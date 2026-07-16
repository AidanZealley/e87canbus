#include <Arduino.h>
#include <EEPROM.h>
#include <SPI.h>
#include <mcp_can.h>

#include "can_ids.h"

#ifndef DEVICE_ID
#define DEVICE_ID 1
#endif

static_assert(DEVICE_ID >= 0 && DEVICE_ID <= 0xFFFF,
              "DEVICE_ID must be an unsigned 16-bit value");

namespace {

const uint8_t CAN_CS_PIN = 10;
const uint32_t CAN_SPEED = CAN_100KBPS;
const uint16_t EEPROM_SESSION_ADDRESS = 0;
const uint32_t HELLO_INTERVAL_MS = 1000;
const uint32_t HEARTBEAT_INTERVAL_MS = 1000;
const uint32_t INCOMPATIBLE_RETRY_MS = 5000;
const uint32_t CONTROLLER_TIMEOUT_MS = 3000;
const int32_t CADENCE_JITTER_MS = 100;
const uint8_t RESPONSE_ACCEPTED = 0;
const uint8_t RESPONSE_UNSUPPORTED = 1;
const uint8_t STATUS_LOCAL_FAULT = 1;
const uint8_t STATUS_CAN_SEND_FAILED = 2;

enum class DeviceState : uint8_t {
    BOOTING,
    DISCOVERING,
    OPERATIONAL,
    CONTROLLER_LOST,
    INCOMPATIBLE,
    LOCAL_FAULT,
};

enum class DisplayMode : uint8_t {
    DISCOVERING,
    NORMAL,
    ERROR,
};

MCP_CAN canBus(CAN_CS_PIN);
DeviceState state = DeviceState::BOOTING;
DisplayMode displayMode = DisplayMode::DISCOVERING;
bool canReady = false;
bool controllerLease = false;
uint16_t deviceSession = 0;
uint16_t controllerSession = 0;
uint8_t latestSequence = 0;
uint8_t deviceStatusCode = 0;
uint32_t lastControllerAckMs = 0;
uint32_t nextHelloMs = 0;
uint32_t nextHeartbeatMs = 0;
uint8_t ledColours[LED_COUNT] = {};

bool due(uint32_t now, uint32_t deadline) {
    return static_cast<int32_t>(now - deadline) >= 0;
}

uint32_t cadence(uint32_t now, uint32_t interval) {
    const int32_t jitter = random(-CADENCE_JITTER_MS, CADENCE_JITTER_MS + 1);
    const int32_t delayMs = static_cast<int32_t>(interval) + jitter;
    return now + static_cast<uint32_t>(delayMs < 0 ? 0 : delayMs);
}

uint16_t getUint16(const uint8_t *payload, uint8_t lowByte, uint8_t highByte) {
    return static_cast<uint16_t>(payload[lowByte]) |
           (static_cast<uint16_t>(payload[highByte]) << 8);
}

void putUint16(uint8_t *payload, uint16_t value, uint8_t lowByte, uint8_t highByte) {
    payload[lowByte] = static_cast<uint8_t>(value & 0xFF);
    payload[highByte] = static_cast<uint8_t>(value >> 8);
}

void selectDisplay(DisplayMode mode) {
    if (displayMode == mode) {
        return;
    }
    displayMode = mode;
    Serial.print("display mode=");
    if (mode == DisplayMode::DISCOVERING) {
        Serial.println("discovering");
    } else if (mode == DisplayMode::NORMAL) {
        Serial.println("normal");
    } else {
        Serial.println("error");
    }
}

void transitionTo(DeviceState nextState) {
    if (state == nextState) {
        return;
    }
    state = nextState;
    Serial.print("device state=");
    switch (nextState) {
        case DeviceState::BOOTING:
            Serial.println("booting");
            break;
        case DeviceState::DISCOVERING:
            Serial.println("discovering");
            break;
        case DeviceState::OPERATIONAL:
            Serial.println("operational");
            break;
        case DeviceState::CONTROLLER_LOST:
            Serial.println("controller_lost");
            break;
        case DeviceState::INCOMPATIBLE:
            Serial.println("incompatible");
            break;
        case DeviceState::LOCAL_FAULT:
            Serial.println("local_fault");
            break;
    }
}

bool readSessionCounter(uint16_t &counter) {
    if (EEPROM.length() < EEPROM_SESSION_ADDRESS + sizeof(counter)) {
        return false;
    }

    uint16_t firstRead = 0;
    uint16_t secondRead = 0;
    EEPROM.get(EEPROM_SESSION_ADDRESS, firstRead);
    EEPROM.get(EEPROM_SESSION_ADDRESS, secondRead);
    if (firstRead != secondRead) {
        return false;
    }
    counter = firstRead;
    return true;
}

bool incrementSession() {
    uint16_t previous = 0;
    if (!readSessionCounter(previous)) {
        return false;
    }

    // uint16_t wrap is intentional: every boot still gets the next modulo-2^16 session.
    deviceSession = static_cast<uint16_t>(previous + 1);
    EEPROM.put(EEPROM_SESSION_ADDRESS, deviceSession);

    uint16_t verified = 0;
    if (!readSessionCounter(verified) || verified != deviceSession) {
        return false;
    }
    return true;
}

void enterLocalFault(uint8_t statusCode, const char *reason) {
    deviceStatusCode = statusCode == 0 ? STATUS_LOCAL_FAULT : statusCode;
    controllerLease = false;
    transitionTo(DeviceState::LOCAL_FAULT);
    selectDisplay(DisplayMode::ERROR);
    Serial.print("local fault reason=");
    Serial.println(reason);
}

bool freshControllerLease(uint32_t now) {
    return controllerLease && (now - lastControllerAckMs <= CONTROLLER_TIMEOUT_MS);
}

bool sendHello(uint32_t now) {
    if (!canReady) {
        return false;
    }

    uint8_t payload[BUTTON_PAD_HELLO_LENGTH] = {};
    latestSequence = static_cast<uint8_t>(latestSequence + 1);
    payload[BUTTON_PAD_HELLO_PROTOCOL_VERSION_BYTE] = CUSTOM_DEVICE_PROTOCOL_VERSION;
    putUint16(payload, static_cast<uint16_t>(DEVICE_ID),
               BUTTON_PAD_HELLO_DEVICE_ID_LOW_BYTE,
               BUTTON_PAD_HELLO_DEVICE_ID_HIGH_BYTE);
    putUint16(payload, deviceSession,
               BUTTON_PAD_HELLO_DEVICE_SESSION_ID_LOW_BYTE,
               BUTTON_PAD_HELLO_DEVICE_SESSION_ID_HIGH_BYTE);
    payload[BUTTON_PAD_HELLO_SEQUENCE_BYTE] = latestSequence;

    const byte status = canBus.sendMsgBuf(CAN_ID_BUTTON_PAD_HELLO, 0,
                                          BUTTON_PAD_HELLO_LENGTH, payload);
    nextHelloMs = state == DeviceState::INCOMPATIBLE
                      ? now + INCOMPATIBLE_RETRY_MS
                      : cadence(now, HELLO_INTERVAL_MS);
    if (status != CAN_OK) {
        Serial.print("HELLO send failed status=");
        Serial.println(status);
        return false;
    }
    return true;
}

bool sendHeartbeat(uint32_t now) {
    if (!canReady || !controllerLease) {
        return false;
    }

    uint8_t payload[BUTTON_PAD_HEARTBEAT_LENGTH] = {};
    latestSequence = static_cast<uint8_t>(latestSequence + 1);
    putUint16(payload, static_cast<uint16_t>(DEVICE_ID),
               BUTTON_PAD_HEARTBEAT_DEVICE_ID_LOW_BYTE,
               BUTTON_PAD_HEARTBEAT_DEVICE_ID_HIGH_BYTE);
    putUint16(payload, deviceSession,
               BUTTON_PAD_HEARTBEAT_DEVICE_SESSION_ID_LOW_BYTE,
               BUTTON_PAD_HEARTBEAT_DEVICE_SESSION_ID_HIGH_BYTE);
    putUint16(payload, controllerSession,
               BUTTON_PAD_HEARTBEAT_CONTROLLER_SESSION_ID_LOW_BYTE,
               BUTTON_PAD_HEARTBEAT_CONTROLLER_SESSION_ID_HIGH_BYTE);
    payload[BUTTON_PAD_HEARTBEAT_SEQUENCE_BYTE] = latestSequence;
    payload[BUTTON_PAD_HEARTBEAT_STATUS_BYTE] = deviceStatusCode;

    const byte status = canBus.sendMsgBuf(CAN_ID_BUTTON_PAD_HEARTBEAT, 0,
                                           BUTTON_PAD_HEARTBEAT_LENGTH, payload);
    nextHeartbeatMs = cadence(now, HEARTBEAT_INTERVAL_MS);
    if (status != CAN_OK) {
        Serial.print("HEARTBEAT send failed status=");
        Serial.println(status);
        if (state == DeviceState::OPERATIONAL) {
            deviceStatusCode = STATUS_CAN_SEND_FAILED;
            transitionTo(DeviceState::LOCAL_FAULT);
            selectDisplay(DisplayMode::ERROR);
        }
        return false;
    }
    return true;
}

void beginDiscovery(uint32_t now, DeviceState discoveryState) {
    controllerSession = 0;
    controllerLease = false;
    transitionTo(discoveryState);
    selectDisplay(discoveryState == DeviceState::CONTROLLER_LOST
                      ? DisplayMode::ERROR
                      : DisplayMode::DISCOVERING);
    nextHelloMs = now;
    sendHello(now);
}

void handleWelcomeAck(const uint8_t *payload, uint8_t length, uint32_t now) {
    if (length != BUTTON_PAD_WELCOME_ACK_LENGTH) {
        Serial.print("ignored malformed WELCOME_ACK length=");
        Serial.println(length);
        return;
    }

    const uint8_t versionAndResponse =
        payload[BUTTON_PAD_WELCOME_ACK_VERSION_AND_RESPONSE_BYTE];
    const uint8_t controllerProtocolVersion = versionAndResponse >> 4;
    const uint8_t responseCode = versionAndResponse & 0x0F;
    const uint16_t acknowledgedDeviceId = getUint16(
        payload, BUTTON_PAD_WELCOME_ACK_DEVICE_ID_LOW_BYTE,
        BUTTON_PAD_WELCOME_ACK_DEVICE_ID_HIGH_BYTE);
    const uint16_t acknowledgedDeviceSession = getUint16(
        payload, BUTTON_PAD_WELCOME_ACK_DEVICE_SESSION_ID_LOW_BYTE,
        BUTTON_PAD_WELCOME_ACK_DEVICE_SESSION_ID_HIGH_BYTE);
    const uint16_t acknowledgedControllerSession = getUint16(
        payload, BUTTON_PAD_WELCOME_ACK_CONTROLLER_SESSION_ID_LOW_BYTE,
        BUTTON_PAD_WELCOME_ACK_CONTROLLER_SESSION_ID_HIGH_BYTE);
    const uint8_t acknowledgedSequence =
        payload[BUTTON_PAD_WELCOME_ACK_DEVICE_SEQUENCE_BYTE];

    if (responseCode != RESPONSE_ACCEPTED && responseCode != RESPONSE_UNSUPPORTED) {
        Serial.print("ignored reserved WELCOME_ACK response=");
        Serial.println(responseCode);
        return;
    }
    if (acknowledgedDeviceId != static_cast<uint16_t>(DEVICE_ID) ||
        acknowledgedDeviceSession != deviceSession ||
        acknowledgedSequence != latestSequence) {
        Serial.println("ignored WELCOME_ACK identity, session, or sequence mismatch");
        return;
    }
    if (responseCode == RESPONSE_UNSUPPORTED) {
        controllerLease = false;
        transitionTo(DeviceState::INCOMPATIBLE);
        selectDisplay(DisplayMode::ERROR);
        nextHelloMs = now + INCOMPATIBLE_RETRY_MS;
        Serial.println("controller rejected protocol version");
        return;
    }
    if (controllerProtocolVersion != CUSTOM_DEVICE_PROTOCOL_VERSION) {
        Serial.println("ignored WELCOME_ACK controller protocol mismatch");
        return;
    }
    if ((state == DeviceState::OPERATIONAL || state == DeviceState::LOCAL_FAULT) &&
        controllerSession != acknowledgedControllerSession) {
        Serial.println("ignored WELCOME_ACK controller session mismatch");
        return;
    }

    controllerSession = acknowledgedControllerSession;
    lastControllerAckMs = now;
    controllerLease = true;
    if (state == DeviceState::DISCOVERING || state == DeviceState::CONTROLLER_LOST ||
        state == DeviceState::INCOMPATIBLE) {
        transitionTo(DeviceState::OPERATIONAL);
        selectDisplay(DisplayMode::NORMAL);
        // The first heartbeat proves the accepted session without waiting a full cadence.
        sendHeartbeat(now);
    }
}

void renderLedSnapshot() {
    Serial.print("received LED snapshot colours=");
    for (uint8_t index = 0; index < LED_COUNT; ++index) {
        if (index > 0) {
            Serial.print(',');
        }
        Serial.print(ledColours[index]);
    }
    Serial.println();
}

void handleLedSnapshot(const uint8_t *payload, uint8_t length, uint32_t now) {
    if (state != DeviceState::OPERATIONAL || !freshControllerLease(now)) {
        return;
    }
    if (length != LED_SNAPSHOT_LENGTH) {
        Serial.print("ignored malformed LED snapshot length=");
        Serial.println(length);
        return;
    }

    uint8_t decoded[LED_COUNT] = {};
    for (uint8_t byteIndex = 0; byteIndex < LED_SNAPSHOT_LENGTH; ++byteIndex) {
        const uint8_t packed = payload[byteIndex];
        const uint8_t evenColour =
            (packed >> LED_EVEN_INDEX_SHIFT) & LED_NIBBLE_MASK;
        const uint8_t oddColour =
            (packed >> LED_ODD_INDEX_SHIFT) & LED_NIBBLE_MASK;
        if (evenColour > LED_COLOUR_MAX || oddColour > LED_COLOUR_MAX) {
            Serial.print("ignored malformed LED snapshot colour byte=");
            Serial.println(byteIndex);
            return;
        }
        decoded[byteIndex * 2] = evenColour;
        decoded[byteIndex * 2 + 1] = oddColour;
    }

    memcpy(ledColours, decoded, sizeof(ledColours));
    renderLedSnapshot();
}

void pollCan(uint32_t now) {
    if (!canReady || canBus.checkReceive() != CAN_MSGAVAIL) {
        return;
    }

    unsigned long arbitrationId = 0;
    uint8_t length = 0;
    uint8_t payload[8] = {};
    canBus.readMsgBuf(&arbitrationId, &length, payload);

    if (arbitrationId == CAN_ID_BUTTON_PAD_WELCOME_ACK) {
        handleWelcomeAck(payload, length, now);
    } else if (arbitrationId == CAN_ID_LED_SNAPSHOT) {
        handleLedSnapshot(payload, length, now);
    }
}

bool sendButtonEvent(uint8_t buttonIndex, bool pressed) __attribute__((unused));

bool sendButtonEvent(uint8_t buttonIndex, bool pressed) {
    if (state != DeviceState::OPERATIONAL || !freshControllerLease(millis()) ||
        buttonIndex >= LED_COUNT) {
        return false;
    }

    uint8_t payload[BUTTON_EVENT_LENGTH] = {
        buttonIndex,
        pressed ? BUTTON_PRESSED : BUTTON_RELEASED,
    };
    const byte status = canBus.sendMsgBuf(CAN_ID_BUTTON_EVENT, 0,
                                          BUTTON_EVENT_LENGTH, payload);
    if (status != CAN_OK) {
        Serial.print("button event send failed status=");
        Serial.println(status);
        return false;
    }
    return true;
}

}  // namespace

void setup() {
    Serial.begin(115200);

    if (!incrementSession()) {
        enterLocalFault(STATUS_LOCAL_FAULT, "EEPROM session read/write verification failed");
        return;
    }
    Serial.print("button pad device id=");
    Serial.print(static_cast<unsigned int>(DEVICE_ID));
    Serial.print(" session=");
    Serial.println(deviceSession);

    const byte status = canBus.begin(MCP_ANY, CAN_SPEED, MCP_16MHZ);
    if (status != CAN_OK) {
        Serial.print("CAN init failed status=");
        Serial.println(status);
        Serial.println("check MCP2515 wiring, CS pin 10, bitrate 100000, and module clock");
        enterLocalFault(STATUS_LOCAL_FAULT, "MCP2515 initialization failed");
        return;
    }

    canBus.setMode(MCP_NORMAL);
    canReady = true;
    Serial.println("CAN init ok at 100000 bit/s; handshake is bench-only");
    beginDiscovery(millis(), DeviceState::DISCOVERING);
}

void loop() {
    const uint32_t now = millis();
    pollCan(now);

    if (state == DeviceState::DISCOVERING || state == DeviceState::CONTROLLER_LOST ||
        state == DeviceState::INCOMPATIBLE) {
        if (due(now, nextHelloMs)) {
            sendHello(now);
        }
        return;
    }

    if (state == DeviceState::OPERATIONAL &&
        (!freshControllerLease(now) || due(now, lastControllerAckMs + CONTROLLER_TIMEOUT_MS))) {
        beginDiscovery(now, DeviceState::CONTROLLER_LOST);
        return;
    }

    if ((state == DeviceState::OPERATIONAL || state == DeviceState::LOCAL_FAULT) &&
        due(now, nextHeartbeatMs)) {
        sendHeartbeat(now);
    }
}
