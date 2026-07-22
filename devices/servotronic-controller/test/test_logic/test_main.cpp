#include <unity.h>
#include "servotronic_logic.h"
#include "registry_protocol.h"
using namespace servotronic;

void test_decoder_is_strict() {
    uint8_t p[] = {0xA9, 0x01}; uint16_t speed = 0;
    TEST_ASSERT_TRUE(decodeSpeed(true, SPEED_CAN_ID, p, 2, speed));
    TEST_ASSERT_EQUAL_UINT16(425, speed);
    TEST_ASSERT_FALSE(decodeSpeed(false, SPEED_CAN_ID, p, 2, speed));
    TEST_ASSERT_FALSE(decodeSpeed(true, SPEED_CAN_ID, p, 1, speed));
    uint8_t high[] = {0xff, 0xff};
    TEST_ASSERT_FALSE(decodeSpeed(true, SPEED_CAN_ID, high, 2, speed));
}
void test_curve_is_monotone_and_bounded() {
    float prior = 1.0f;
    for (uint16_t s = 0; s <= MAX_SPEED_DECI_KPH; ++s) {
        float value = assistanceForSpeed(s);
        TEST_ASSERT_TRUE(value <= prior + 0.000001f); prior = value;
    }
    TEST_ASSERT_FLOAT_WITHIN(0.000001f, 1.0f, assistanceForSpeed(0));
    TEST_ASSERT_FLOAT_WITHIN(0.000001f, 0.722010416666667f, assistanceForSpeed(250));
    TEST_ASSERT_FLOAT_WITHIN(0.000001f, 0.519580357142857f, assistanceForSpeed(450));
    TEST_ASSERT_FLOAT_WITHIN(0.000001f, 0.14285119047619f, assistanceForSpeed(800));
    TEST_ASSERT_FLOAT_WITHIN(0.000001f, 0.0f, assistanceForSpeed(1000));
    TEST_ASSERT_EQUAL_UINT8(90, boundedDuty(0.5f, 180));
}
void test_failsafe_precedence_and_timeout() {
    SpeedState s;
    TEST_ASSERT_EQUAL(Inhibit::NO_SPEED, inhibitReason(s, 1, true));
    s.seen = true; s.receivedMs = 100;
    TEST_ASSERT_EQUAL(Inhibit::NONE, inhibitReason(s, 600, true));
    TEST_ASSERT_EQUAL(Inhibit::STALE_SPEED, inhibitReason(s, 601, true));
    s.invalid = true;
    TEST_ASSERT_EQUAL(Inhibit::INVALID_SPEED, inhibitReason(s, 101, true));
    TEST_ASSERT_EQUAL(Inhibit::CAN_FAULT, inhibitReason(s, 101, false));
}
void test_ack_tracker_refreshes_hello_and_heartbeat() {
    AckTracker tracker;
    TEST_ASSERT_FALSE(tracker.accept(0, 0x1234));
    tracker.expect(AckKind::HELLO, 9);
    TEST_ASSERT_FALSE(tracker.accept(8, 0x1234));
    TEST_ASSERT_TRUE(tracker.accept(9, 0x1234));
    TEST_ASSERT_EQUAL_UINT16(0x1234, tracker.controllerSession);
    TEST_ASSERT_FALSE(tracker.accept(9, 0x1234));
    tracker.expect(AckKind::HEARTBEAT, 10);
    TEST_ASSERT_FALSE(tracker.accept(10, 0x5678));
    TEST_ASSERT_TRUE(tracker.accept(10, 0x1234));
}
void test_curve_activation_is_validated_and_atomic() {
    uint8_t payload[CURVE_PAYLOAD_LENGTH] = {};
    payload[0] = CURVE_PROTOCOL_VERSION; payload[1] = CURVE_SET_OPCODE;
    payload[2] = CURVE_SCHEMA_VERSION; payload[3] = CURVE_INTERPOLATION_VERSION;
    writeU32(payload + 4, 7);
    const uint16_t speeds[] = {0, 100, 200, 300, 600, 1000, 1600, 2500};
    const uint16_t values[] = {900, 800, 700, 600, 400, 200, 100, 0};
    for (uint8_t i = 0; i < CURVE_POINT_COUNT; ++i) {
        writeU16(payload + 8 + i * 2, speeds[i]);
        writeU16(payload + 24 + i * 2, values[i]);
    }
    writeU32(payload + 40, crc32(payload, 40));
    ActiveCurve active;
    TEST_ASSERT_EQUAL(CurveResult::ACCEPTED, applyCurvePayload(payload, sizeof(payload), active));
    TEST_ASSERT_EQUAL(CurveSource::COORDINATOR_RAM, active.source);
    TEST_ASSERT_EQUAL_UINT32(7, active.revision);
    TEST_ASSERT_EQUAL_UINT16(900, active.assistance[0]);
    // Curve selection has no coordinator-lease input: accepted RAM remains active, while
    // direct speed freshness still independently gates whether PWM may be applied.
    SpeedState freshSpeed;
    freshSpeed.seen = true; freshSpeed.receivedMs = 100;
    TEST_ASSERT_EQUAL(Inhibit::NONE, inhibitReason(freshSpeed, 100, true));
    TEST_ASSERT_EQUAL_UINT16(900, active.assistance[0]);
    TEST_ASSERT_EQUAL(Inhibit::STALE_SPEED, inhibitReason(freshSpeed, 601, true));
    TEST_ASSERT_EQUAL_UINT16(900, active.assistance[0]);

    const uint32_t acceptedCrc = active.crc32;
    payload[24] ^= 1;
    TEST_ASSERT_EQUAL(CurveResult::BAD_CRC, applyCurvePayload(payload, sizeof(payload), active));
    TEST_ASSERT_EQUAL_UINT32(acceptedCrc, active.crc32);
    TEST_ASSERT_EQUAL_UINT16(900, active.assistance[0]);

    payload[24] ^= 1;  // restore accepted value
    payload[2] = 2; writeU32(payload + 40, crc32(payload, 40));
    TEST_ASSERT_EQUAL(CurveResult::UNSUPPORTED, applyCurvePayload(payload, sizeof(payload), active));
    payload[2] = CURVE_SCHEMA_VERSION;
    writeU16(payload + 8, 1); writeU32(payload + 40, crc32(payload, 40));
    TEST_ASSERT_EQUAL(CurveResult::BAD_GRID, applyCurvePayload(payload, sizeof(payload), active));
    writeU16(payload + 8, 0);
    writeU16(payload + 24, 1001); writeU32(payload + 40, crc32(payload, 40));
    TEST_ASSERT_EQUAL(CurveResult::BAD_VALUES, applyCurvePayload(payload, sizeof(payload), active));
    writeU16(payload + 24, 900); writeU16(payload + 26, 901);
    writeU32(payload + 40, crc32(payload, 40));
    TEST_ASSERT_EQUAL(CurveResult::BAD_VALUES, applyCurvePayload(payload, sizeof(payload), active));
    TEST_ASSERT_EQUAL(CurveResult::BAD_LENGTH,
                      applyCurvePayload(payload, sizeof(payload) - 1, active));
    TEST_ASSERT_EQUAL_UINT32(acceptedCrc, active.crc32);
}
void test_manual_control_payload_is_validated_atomically() {
    ControlCommand control;
    uint8_t payload[] = {CURVE_PROTOCOL_VERSION, CONTROL_SET_OPCODE, 0xEE, 0x02,
                         static_cast<uint8_t>(ControlMode::MANUAL)};
    TEST_ASSERT_TRUE(applyControlPayload(payload, sizeof(payload), control));
    TEST_ASSERT_EQUAL(ControlMode::MANUAL, control.mode);
    TEST_ASSERT_EQUAL_UINT16(750, control.assistancePerMille);
    payload[2] = 0xE9; payload[3] = 0x03;
    TEST_ASSERT_FALSE(applyControlPayload(payload, sizeof(payload), control));
    TEST_ASSERT_EQUAL_UINT16(750, control.assistancePerMille);
}
int main(int, char **) {
    UNITY_BEGIN(); RUN_TEST(test_decoder_is_strict); RUN_TEST(test_curve_is_monotone_and_bounded);
    RUN_TEST(test_failsafe_precedence_and_timeout);
    RUN_TEST(test_ack_tracker_refreshes_hello_and_heartbeat);
    RUN_TEST(test_curve_activation_is_validated_and_atomic);
    RUN_TEST(test_manual_control_payload_is_validated_atomically); return UNITY_END();
}
