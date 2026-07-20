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
    TEST_ASSERT_EQUAL(Inhibit::NO_SPEED, inhibitReason(s, 1, true, true));
    s.seen = true; s.receivedMs = 100;
    TEST_ASSERT_EQUAL(Inhibit::NONE, inhibitReason(s, 600, true, true));
    TEST_ASSERT_EQUAL(Inhibit::STALE_SPEED, inhibitReason(s, 601, true, true));
    s.invalid = true;
    TEST_ASSERT_EQUAL(Inhibit::INVALID_SPEED, inhibitReason(s, 101, true, true));
    TEST_ASSERT_EQUAL(Inhibit::NO_CONTROLLER, inhibitReason(s, 101, false, true));
    TEST_ASSERT_EQUAL(Inhibit::CAN_FAULT, inhibitReason(s, 101, true, false));
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
int main(int, char **) {
    UNITY_BEGIN(); RUN_TEST(test_decoder_is_strict); RUN_TEST(test_curve_is_monotone_and_bounded);
    RUN_TEST(test_failsafe_precedence_and_timeout);
    RUN_TEST(test_ack_tracker_refreshes_hello_and_heartbeat); return UNITY_END();
}
