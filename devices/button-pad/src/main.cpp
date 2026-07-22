#include <Adafruit_NeoTrellis.h>
#include <Arduino.h>
#include <EEPROM.h>
#include <SPI.h>
#include <Wire.h>
#include <mcp_can.h>

#include "can_ids.h"
#include "button_pad_effects.h"
#include "isotp_transport.h"
#include "protocol_state.h"

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
const uint8_t BUTTON_PAD_EFFECT_COMMAND_VERSION = 1;
const uint8_t BUTTON_LED_COUNT = 16;
const uint8_t TRELLIS_ADDR = 0x2E;
const uint8_t TRELLIS_BRIGHTNESS = 20;
const uint32_t TRELLIS_POLL_MS = 20;
const uint32_t TRELLIS_ANIMATION_FRAME_MS = 80;
const uint8_t TRELLIS_PIXEL_CHUNK_BYTES = 24;
const uint16_t DISCOVERY_BREATHE_PERIOD_MS = 1600;
const uint8_t DISCOVERY_BREATHE_MINIMUM = 16;
using button_pad::DeviceState;
using button_pad::STATUS_CAN_SEND_FAILED;
using button_pad::STATUS_LOCAL_FAULT;

enum class DisplayMode : uint8_t {
    DISCOVERING,
    NORMAL,
    ERROR,
};

MCP_CAN canBus(CAN_CS_PIN);
Adafruit_NeoTrellis trellis(TRELLIS_ADDR);

bool sendIsoTpFrame(uint32_t arbitrationId, const uint8_t *payload, uint8_t length) {
    return canBus.sendMsgBuf(arbitrationId, 0, length, const_cast<uint8_t *>(payload)) == CAN_OK;
}

e87canbus::IsoTpTransport transport(CAN_ID_BUTTON_PAD_TRANSPORT_DEVICE_TO_COORDINATOR,
                                    sendIsoTpFrame);
DeviceState state = DeviceState::BOOTING;
DisplayMode displayMode = DisplayMode::DISCOVERING;
bool canReady = false;
bool canTransmitFault = false;
bool trellisReady = false;
bool controllerLease = false;
uint16_t deviceSession = 0;
uint16_t controllerSession = 0;
button_pad::SequenceState sequences;
uint8_t deviceStatusCode = 0;
uint32_t lastControllerAckMs = 0;
uint32_t nextHelloMs = 0;
uint32_t nextHeartbeatMs = 0;
uint32_t nextTrellisPollMs = 0;
uint32_t nextTrellisAnimationFrameMs = 0;
e87canbus::ButtonPadEffects effects;
uint8_t renderedPixels[e87canbus::BUTTON_PAD_RGB_BYTES] = {};

bool due(uint32_t now, uint32_t deadline) {
    return static_cast<int32_t>(now - deadline) >= 0;
}

uint32_t cadence(uint32_t now, uint32_t interval) {
    const int32_t jitter = random(-CADENCE_JITTER_MS, CADENCE_JITTER_MS + 1);
    const int32_t delayMs = static_cast<int32_t>(interval) + jitter;
    return now + static_cast<uint32_t>(delayMs < 0 ? 0 : delayMs);
}

uint8_t scalePixelChannel(uint8_t value) {
    if (value == 0 || TRELLIS_BRIGHTNESS == 0) {
        return 0;
    }
    // The coordinator intentionally uses low RGB values for assigned-button
    // illumination. Round non-zero values up so the hardware brightness
    // ceiling does not truncate those soft colours to black.
    return static_cast<uint8_t>(
        (static_cast<uint16_t>(value) * TRELLIS_BRIGHTNESS + 255) >> 8);
}

uint16_t getUint16(const uint8_t *payload, uint8_t lowByte, uint8_t highByte) {
    return static_cast<uint16_t>(payload[lowByte]) |
           (static_cast<uint16_t>(payload[highByte]) << 8);
}

void applyPixelDisplay(uint32_t now) {
    if (!trellisReady) {
        return;
    }
    if (displayMode == DisplayMode::NORMAL) {
        effects.render(now, renderedPixels);
    } else if (displayMode == DisplayMode::DISCOVERING) {
        const uint16_t halfPeriod = DISCOVERY_BREATHE_PERIOD_MS / 2;
        const uint16_t phase = static_cast<uint16_t>(now % DISCOVERY_BREATHE_PERIOD_MS);
        const uint16_t ramp = phase <= halfPeriod ? phase : DISCOVERY_BREATHE_PERIOD_MS - phase;
        const uint8_t brightness = static_cast<uint8_t>(
            DISCOVERY_BREATHE_MINIMUM +
            (static_cast<uint32_t>(128 - DISCOVERY_BREATHE_MINIMUM) * ramp) / halfPeriod);
        for (uint8_t i = 0; i < BUTTON_LED_COUNT; i++) {
            renderedPixels[i * 3] = brightness;
            renderedPixels[i * 3 + 1] = brightness;
            renderedPixels[i * 3 + 2] = brightness;
        }
    } else {
        for (uint8_t i = 0; i < BUTTON_LED_COUNT; i++) {
            renderedPixels[i * 3] = 0x20;
            renderedPixels[i * 3 + 1] = 0;
            renderedPixels[i * 3 + 2] = 0;
        }
    }

    // seesaw_NeoPixel::setPixelColor performs one I2C transaction per LED.
    // Write the remote GRB buffer in two bounded chunks instead, reducing a
    // full-pad frame from 16 transactions to two. Four protocol bytes plus
    // 24 data bytes remain below the AVR Wire buffer limit.
    uint8_t grb[e87canbus::BUTTON_PAD_RGB_BYTES] = {};
    for (uint8_t i = 0; i < BUTTON_LED_COUNT; i++) {
        grb[i * 3] = scalePixelChannel(renderedPixels[i * 3 + 1]);
        grb[i * 3 + 1] = scalePixelChannel(renderedPixels[i * 3]);
        grb[i * 3 + 2] = scalePixelChannel(renderedPixels[i * 3 + 2]);
    }
    for (uint8_t offset = 0; offset < sizeof(grb); offset += TRELLIS_PIXEL_CHUNK_BYTES) {
        Wire.beginTransmission(TRELLIS_ADDR);
        Wire.write(SEESAW_NEOPIXEL_BASE);
        Wire.write(SEESAW_NEOPIXEL_BUF);
        Wire.write(static_cast<uint8_t>(0));
        Wire.write(offset);
        Wire.write(grb + offset, TRELLIS_PIXEL_CHUNK_BYTES);
        Wire.endTransmission();
    }
    trellis.pixels.show();
    nextTrellisAnimationFrameMs = now + TRELLIS_ANIMATION_FRAME_MS;
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
    applyPixelDisplay(millis());
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
    transitionTo(DeviceState::LOCAL_FAULT);
    selectDisplay(DisplayMode::ERROR);
    Serial.print("local fault reason=");
    Serial.println(reason);
}

bool freshControllerLease(uint32_t now) {
    return controllerLease && (now - lastControllerAckMs <= CONTROLLER_TIMEOUT_MS);
}

bool initializeCanController() {
    const byte status = canBus.begin(MCP_ANY, CAN_SPEED, MCP_8MHZ);
    if (status != CAN_OK) {
        canReady = false;
        Serial.print("CAN initialization failed status=");
        Serial.println(status);
        return false;
    }

    canBus.setMode(MCP_NORMAL);
    canReady = true;
    canTransmitFault = false;
    return true;
}

bool sendHello(uint32_t now) {
    // With the Pi powered down there may be nobody left to ACK CAN frames. The
    // MCP2515 then eventually enters bus-off, which persists after the Pi comes
    // back. Reinitializing after a failed transmit resets its error counters so
    // the next discovery attempt can actually reach the restarted coordinator.
    if (canTransmitFault && !initializeCanController()) {
        nextHelloMs = cadence(now, HELLO_INTERVAL_MS);
        return false;
    }
    if (!canReady) {
        return false;
    }

    uint8_t payload[BUTTON_PAD_HELLO_LENGTH] = {};
    const uint8_t sequence = sequences.nextHello();
    button_pad::encodeHello(payload, CUSTOM_DEVICE_PROTOCOL_VERSION,
                            static_cast<uint16_t>(DEVICE_ID), deviceSession, sequence);

    const byte status = canBus.sendMsgBuf(CAN_ID_BUTTON_PAD_HELLO, 0,
                                          BUTTON_PAD_HELLO_LENGTH, payload);
    nextHelloMs = state == DeviceState::INCOMPATIBLE
                      ? now + INCOMPATIBLE_RETRY_MS
                      : cadence(now, HELLO_INTERVAL_MS);
    if (status != CAN_OK) {
        canTransmitFault = true;
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
    const uint8_t sequence = sequences.nextHeartbeat();
    button_pad::encodeHeartbeat(payload, static_cast<uint16_t>(DEVICE_ID), deviceSession,
                                controllerSession, sequence, deviceStatusCode);

    const byte status = canBus.sendMsgBuf(CAN_ID_BUTTON_PAD_HEARTBEAT, 0,
                                           BUTTON_PAD_HEARTBEAT_LENGTH, payload);
    nextHeartbeatMs = cadence(now, HEARTBEAT_INTERVAL_MS);
    const button_pad::DeviceStatus sendResult = button_pad::heartbeatSendCompleted(
        {state, deviceStatusCode}, status == CAN_OK);
    if (status != CAN_OK) {
        canTransmitFault = true;
        Serial.print("HEARTBEAT send failed status=");
        Serial.println(status);
        deviceStatusCode = sendResult.code;
        if (state != sendResult.state) {
            transitionTo(sendResult.state);
            selectDisplay(DisplayMode::ERROR);
        }
        return false;
    }
    if (state != sendResult.state) {
        deviceStatusCode = sendResult.code;
        transitionTo(sendResult.state);
        selectDisplay(DisplayMode::NORMAL);
        Serial.println("heartbeat send recovered; transient CAN fault cleared");
    }
    return true;
}

void beginDiscovery(uint32_t now, DeviceState discoveryState) {
    controllerSession = 0;
    controllerLease = false;
    transitionTo(discoveryState);
    // A missing controller is an expected recovery state while the Pi boots or
    // reboots. Keep breathing white until a WELCOME arrives; ERROR is reserved
    // for an explicit incompatibility or a local device/transport fault.
    selectDisplay(DisplayMode::DISCOVERING);
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
        acknowledgedSequence != sequences.lastSent) {
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
        if (deviceStatusCode == 0) {
            transitionTo(DeviceState::OPERATIONAL);
            selectDisplay(DisplayMode::NORMAL);
        } else {
            transitionTo(DeviceState::LOCAL_FAULT);
            selectDisplay(DisplayMode::ERROR);
        }
        // The first heartbeat proves the accepted session without waiting a full cadence.
        sendHeartbeat(now);
    }
}

void handleButtonPadEffect(const uint8_t *payload, uint8_t length, uint32_t now) {
    if (state != DeviceState::OPERATIONAL || !freshControllerLease(now) ||
        length != BUTTON_PAD_EFFECT_LENGTH ||
        payload[BUTTON_PAD_EFFECT_VERSION_BYTE] != BUTTON_PAD_EFFECT_COMMAND_VERSION ||
        payload[BUTTON_PAD_EFFECT_BUTTON_INDEX_BYTE] >= BUTTON_LED_COUNT ||
        payload[BUTTON_PAD_EFFECT_RESERVED_5_BYTE] != 0 ||
        payload[BUTTON_PAD_EFFECT_RESERVED_6_BYTE] != 0 ||
        payload[BUTTON_PAD_EFFECT_RESERVED_7_BYTE] != 0) {
        return;
    }
    const uint8_t opcode = payload[BUTTON_PAD_EFFECT_OPCODE_BYTE];
    const uint8_t buttonIndex = payload[BUTTON_PAD_EFFECT_BUTTON_INDEX_BYTE];
    bool applied = false;
    if ((opcode == BUTTON_PAD_EFFECT_BLINK_RED_DOUBLE ||
         opcode == BUTTON_PAD_EFFECT_BLINK_WHITE_SINGLE ||
         opcode == BUTTON_PAD_EFFECT_BLINK_AMBER_DOUBLE) &&
        payload[BUTTON_PAD_EFFECT_ENABLED_BYTE] == 1) {
        const uint8_t red = opcode == BUTTON_PAD_EFFECT_BLINK_AMBER_DOUBLE ? 255 :
                            opcode == BUTTON_PAD_EFFECT_BLINK_WHITE_SINGLE ? 255 : 255;
        const uint8_t green = opcode == BUTTON_PAD_EFFECT_BLINK_AMBER_DOUBLE ? 191 :
                              opcode == BUTTON_PAD_EFFECT_BLINK_WHITE_SINGLE ? 255 : 0;
        const uint8_t blue = opcode == BUTTON_PAD_EFFECT_BLINK_AMBER_DOUBLE ? 0 :
                             opcode == BUTTON_PAD_EFFECT_BLINK_WHITE_SINGLE ? 255 : 0;
        applied = opcode == BUTTON_PAD_EFFECT_BLINK_WHITE_SINGLE
                      ? effects.triggerSingleBlink(buttonIndex, red, green, blue, now)
                      : effects.triggerDoubleBlink(buttonIndex, red, green, blue, now);
    } else if (opcode == BUTTON_PAD_EFFECT_BREATHE &&
               payload[BUTTON_PAD_EFFECT_ENABLED_BYTE] <= 1) {
        applied = effects.setBreathe(buttonIndex, payload[BUTTON_PAD_EFFECT_ENABLED_BYTE] == 1);
    }
    if (applied && displayMode == DisplayMode::NORMAL) {
        applyPixelDisplay(now);
    }
}

void pollCan(uint32_t now) {
    while (canReady && canBus.checkReceive() == CAN_MSGAVAIL) {
        unsigned long arbitrationId = 0;
        uint8_t length = 0;
        uint8_t payload[8] = {};
        canBus.readMsgBuf(&arbitrationId, &length, payload);

        if (arbitrationId == CAN_ID_BUTTON_PAD_WELCOME_ACK) {
            handleWelcomeAck(payload, length, now);
        } else if (arbitrationId == CAN_ID_BUTTON_PAD_EFFECT) {
            handleButtonPadEffect(payload, length, now);
        } else if (arbitrationId == CAN_ID_BUTTON_PAD_TRANSPORT_COORDINATOR_TO_DEVICE) {
            transport.onFrame(payload, length);
        }
    }
}

bool sendButtonEvent(uint8_t buttonIndex, bool pressed) {
    if (state != DeviceState::OPERATIONAL || !freshControllerLease(millis()) ||
        buttonIndex >= BUTTON_LED_COUNT) {
        return false;
    }

    uint8_t payload[BUTTON_EVENT_LENGTH] = {
        buttonIndex,
        pressed ? BUTTON_PRESSED : BUTTON_RELEASED,
    };
    const byte status = canBus.sendMsgBuf(CAN_ID_BUTTON_EVENT, 0,
                                          BUTTON_EVENT_LENGTH, payload);
    if (status != CAN_OK) {
        canTransmitFault = true;
        Serial.print("button event send failed status=");
        Serial.println(status);
        return false;
    }
    return true;
}

// Seesaw hardware debounces; rising = pressed, falling = released.
// Physical key index maps 1:1 to logical index 0–15 (row-major, top-left = 0).
TrellisCallback onTrellisKey(keyEvent evt) {
    sendButtonEvent(evt.bit.NUM, evt.bit.EDGE == SEESAW_KEYPAD_EDGE_RISING);
    return nullptr;
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

    // This MCP2515 module has an 8 MHz crystal; this is independent of the
    // Pro Micro's 16 MHz ATmega32U4 CPU clock.
    if (!initializeCanController()) {
        Serial.println("check MCP2515 wiring, CS pin 10, bitrate 100000, and module clock");
        enterLocalFault(STATUS_LOCAL_FAULT, "MCP2515 initialization failed");
        return;
    }

    Serial.println("CAN init ok at 100000 bit/s; handshake is controller-managed");

    // NeoTrellis on hardware I²C: SDA=D2, SCL=D3 (ATmega32U4 TWI).
    Wire.begin();
    if (!trellis.begin()) {
        Serial.println("NeoTrellis init failed - check I2C wiring and address 0x2E");
    } else {
        trellisReady = true;
        trellis.pixels.setBrightness(TRELLIS_BRIGHTNESS);
        for (uint8_t i = 0; i < BUTTON_LED_COUNT; i++) {
            trellis.activateKey(i, SEESAW_KEYPAD_EDGE_RISING);
            trellis.activateKey(i, SEESAW_KEYPAD_EDGE_FALLING);
            trellis.registerCallback(i, onTrellisKey);
        }
        Serial.println("NeoTrellis init ok at 0x2E");
    }

    beginDiscovery(millis(), DeviceState::DISCOVERING);
}

void loop() {
    const uint32_t now = millis();
    pollCan(now);
    transport.poll();

    uint8_t transportPayload[e87canbus::ISOTP_MAXIMUM_PAYLOAD_LENGTH] = {};
    uint16_t transportLength = 0;
    if (transport.receive(transportPayload, sizeof(transportPayload), &transportLength)) {
        if (effects.apply(transportPayload, transportLength, now)) {
            if (displayMode == DisplayMode::NORMAL && effects.committed()) {
                applyPixelDisplay(now);
            }
        } else {
            Serial.print("ignored malformed button-pad program length=");
            Serial.println(transportLength);
        }
    }

    if (trellisReady && due(now, nextTrellisPollMs)) {
        trellis.read();
        nextTrellisPollMs = now + TRELLIS_POLL_MS;
        const bool animationNeedsFrame =
            (displayMode == DisplayMode::NORMAL && effects.animated(now)) ||
            displayMode == DisplayMode::DISCOVERING;
        if (animationNeedsFrame && due(now, nextTrellisAnimationFrameMs)) {
            applyPixelDisplay(now);
        }
    }

    if (state == DeviceState::DISCOVERING || state == DeviceState::CONTROLLER_LOST ||
        state == DeviceState::INCOMPATIBLE) {
        if (due(now, nextHelloMs)) {
            sendHello(now);
        }
        return;
    }

    if (button_pad::shouldBeginDiscovery(
            state, controllerLease, freshControllerLease(now))) {
        beginDiscovery(now, DeviceState::CONTROLLER_LOST);
        return;
    }

    if ((state == DeviceState::OPERATIONAL || state == DeviceState::LOCAL_FAULT) &&
        due(now, nextHeartbeatMs)) {
        sendHeartbeat(now);
    }
}
