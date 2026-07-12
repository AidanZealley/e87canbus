#include <Arduino.h>
#include <SPI.h>
#include <mcp_can.h>

#include "can_ids.h"

static const uint8_t CAN_CS_PIN = 10;
static const uint32_t CAN_SPEED = CAN_500KBPS;
static const uint32_t SEND_INTERVAL_MS = 1000;

MCP_CAN canBus(CAN_CS_PIN);
bool nextPressed = true;
uint32_t lastSendMs = 0;

bool sendButtonEvent(uint8_t buttonIndex, bool pressed) {
    uint8_t payload[BUTTON_EVENT_LENGTH] = {
        buttonIndex,
        pressed ? BUTTON_PRESSED : BUTTON_RELEASED,
    };
    const byte status = canBus.sendMsgBuf(CAN_ID_BUTTON_EVENT, 0, BUTTON_EVENT_LENGTH, payload);
    if (status != CAN_OK) {
        Serial.print("failed to send button event status=");
        Serial.println(status);
        return false;
    }

    Serial.print("sent button event index=");
    Serial.print(buttonIndex);
    Serial.print(" state=");
    Serial.println(pressed ? "pressed" : "released");
    return true;
}

void handleLedUpdate(const uint8_t *payload, uint8_t length) {
    if (length != LED_UPDATE_LENGTH) {
        Serial.print("ignored malformed led update length=");
        Serial.println(length);
        return;
    }

    const uint8_t buttonIndex = payload[LED_UPDATE_INDEX_BYTE];
    const uint8_t colourCode = payload[LED_UPDATE_COLOUR_BYTE];

    Serial.print("received led update index=");
    Serial.print(buttonIndex);
    Serial.print(" colour=");
    Serial.println(colourCode);
}

void pollCan() {
    if (canBus.checkReceive() != CAN_MSGAVAIL) {
        return;
    }

    unsigned long arbitrationId = 0;
    uint8_t length = 0;
    uint8_t payload[8] = {};
    canBus.readMsgBuf(&arbitrationId, &length, payload);

    if (arbitrationId == CAN_ID_LED_UPDATE) {
        handleLedUpdate(payload, length);
    }
}

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000) {
        delay(10);
    }

    const byte status = canBus.begin(MCP_ANY, CAN_SPEED, MCP_16MHZ);
    if (status != CAN_OK) {
        Serial.print("CAN init failed status=");
        Serial.println(status);
        Serial.println("check MCP2515 wiring, CS pin 10, bitrate 500000, and module clock");
        return;
    }

    canBus.setMode(MCP_NORMAL);
    Serial.println("CAN init ok");
}

void loop() {
    pollCan();

    const uint32_t now = millis();
    if (now - lastSendMs >= SEND_INTERVAL_MS) {
        lastSendMs = now;
        if (sendButtonEvent(0, nextPressed)) {
            nextPressed = !nextPressed;
        }
    }
}
