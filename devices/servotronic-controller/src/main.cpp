#include <Arduino.h>
#include <EEPROM.h>
#include <SPI.h>
#include <avr/wdt.h>
#include <mcp_can.h>

#include "registry_protocol.h"
#include "servotronic_logic.h"

#ifndef DEVICE_ID
#define DEVICE_ID 1
#endif
#ifndef CAN_CS_PIN
#define CAN_CS_PIN 10
#endif
#ifndef MCP2515_CLOCK
#define MCP2515_CLOCK MCP_8MHZ
#endif
#ifndef PWM_OUTPUT_PIN
#define PWM_OUTPUT_PIN 9
#endif
#ifndef PWM_DUTY_CEILING
#define PWM_DUTY_CEILING 180
#endif
static_assert(DEVICE_ID >= 0 && DEVICE_ID <= 0xffff, "DEVICE_ID must fit uint16_t");
static_assert(PWM_DUTY_CEILING >= 0 && PWM_DUTY_CEILING <= 255,
              "PWM_DUTY_CEILING must fit analogWrite");

namespace {
constexpr uint32_t HELLO_MS = 1000, HEARTBEAT_MS = 1000, LEASE_MS = 3000;
MCP_CAN bus(CAN_CS_PIN);
servotronic::SpeedState speed;
bool canHealthy = false, leased = false;
uint16_t deviceSession = 0, controllerSession = 0;
uint8_t sequence = 0;
servotronic::AckTracker acknowledgements;
uint32_t lastAckMs = 0, nextHelloMs = 0, nextHeartbeatMs = 0, nextCanRetryMs = 0, nextDiagnosticMs = 0;
servotronic::Inhibit lastInhibit = servotronic::Inhibit::NO_SPEED;

bool due(uint32_t now, uint32_t deadline) { return static_cast<int32_t>(now - deadline) >= 0; }
bool leaseFresh(uint32_t now) { return leased && now - lastAckMs <= LEASE_MS; }
void safeOff() { analogWrite(PWM_OUTPUT_PIN, 0); }

bool initializeCan() {
    safeOff();
    if (bus.begin(MCP_ANY, CAN_100KBPS, MCP2515_CLOCK) != CAN_OK) return canHealthy = false;
    bus.setMode(MCP_NORMAL);
    return canHealthy = true;
}

void sendHello(uint32_t now) {
    uint8_t p[8] = {};
    const uint8_t sentSequence = sequence++;
    servotronic::encodeHello(p, DEVICE_ID, deviceSession, sentSequence);
    acknowledgements.expect(servotronic::AckKind::HELLO, sentSequence);
    if (!canHealthy || bus.sendMsgBuf(servotronic::HELLO_ID, 0, 8, p) != CAN_OK) canHealthy = false;
    nextHelloMs = now + HELLO_MS;
}

void sendHeartbeat(uint32_t now, uint8_t status) {
    uint8_t p[8] = {};
    const uint8_t sentSequence = sequence++;
    servotronic::encodeHeartbeat(p, DEVICE_ID, deviceSession, controllerSession, sentSequence, status);
    acknowledgements.expect(servotronic::AckKind::HEARTBEAT, sentSequence);
    if (bus.sendMsgBuf(servotronic::HEARTBEAT_ID, 0, 8, p) != CAN_OK) canHealthy = false;
    nextHeartbeatMs = now + HEARTBEAT_MS;
}

void handleWelcome(const uint8_t *p, uint8_t length, uint32_t now) {
    if (length != 8 || servotronic::u16(p, 1) != DEVICE_ID ||
        servotronic::u16(p, 3) != deviceSession) return;
    const uint8_t response = p[0] & 0x0f, version = p[0] >> 4;
    if (response != 0 || version != servotronic::PROTOCOL_VERSION) { leased = false; return; }
    const uint16_t acknowledgedSession = servotronic::u16(p, 5);
    if (!acknowledgements.accept(p[7], acknowledgedSession)) return;
    controllerSession = acknowledgedSession; lastAckMs = now; leased = true;
}

void pollCan(uint32_t now) {
    while (canHealthy && bus.checkReceive() == CAN_MSGAVAIL) {
        unsigned long id = 0; uint8_t extendedFlag = 0, length = 0; uint8_t p[8] = {};
        bus.readMsgBuf(&id, &extendedFlag, &length, p);
        const bool extended = extendedFlag != 0;
        if (!extended && id == servotronic::WELCOME_ID) handleWelcome(p, length, now);
        if ((id & 0x1fffffffUL) == servotronic::SPEED_CAN_ID) {
            uint16_t value = 0;
            if (servotronic::decodeSpeed(extended, id & 0x1fffffffUL, p, length, value)) {
                speed.seen = true; speed.invalid = false; speed.deciKph = value; speed.receivedMs = now;
            } else {
                speed.invalid = true;
            }
        }
    }
    if (canHealthy && bus.checkError() != CAN_OK) canHealthy = false;
}

const char *inhibitName(servotronic::Inhibit r) {
    switch (r) {
        case servotronic::Inhibit::NONE: return "none";
        case servotronic::Inhibit::NO_SPEED: return "no_speed";
        case servotronic::Inhibit::STALE_SPEED: return "stale_speed";
        case servotronic::Inhibit::INVALID_SPEED: return "invalid_speed";
        case servotronic::Inhibit::NO_CONTROLLER: return "no_controller";
        default: return "can_fault";
    }
}
}  // namespace

void setup() {
    MCUSR = 0;
    wdt_disable();
    pinMode(PWM_OUTPUT_PIN, OUTPUT); safeOff();
    Serial.begin(115200);
    EEPROM.get(0, deviceSession); ++deviceSession; EEPROM.put(0, deviceSession);
    initializeCan();
    nextHelloMs = millis();
    wdt_enable(WDTO_1S);
}

void loop() {
    wdt_reset();
    const uint32_t now = millis();
    pollCan(now);
    if (!canHealthy && due(now, nextCanRetryMs)) {
        initializeCan(); nextCanRetryMs = now + 1000; leased = false;
    }
    if (!leaseFresh(now)) leased = false;
    if (!leased && due(now, nextHelloMs)) sendHello(now);
    const servotronic::Inhibit inhibit = servotronic::inhibitReason(speed, now, leaseFresh(now), canHealthy);
    const float assistance = servotronic::assistanceForSpeed(speed.deciKph);
    const uint8_t duty = inhibit == servotronic::Inhibit::NONE
                             ? servotronic::boundedDuty(assistance, PWM_DUTY_CEILING) : 0;
    analogWrite(PWM_OUTPUT_PIN, duty);
    if (leased && due(now, nextHeartbeatMs)) sendHeartbeat(now, static_cast<uint8_t>(inhibit));
    if (inhibit != lastInhibit || due(now, nextDiagnosticMs)) {
        Serial.print("speed_dkph="); Serial.print(speed.deciKph);
        Serial.print(" assistance="); Serial.print(assistance, 4);
        Serial.print(" duty="); Serial.print(duty);
        Serial.print(" inhibit="); Serial.println(inhibitName(inhibit));
        lastInhibit = inhibit; nextDiagnosticMs = now + 1000;
    }
}
