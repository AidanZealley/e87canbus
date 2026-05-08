#include <Arduino.h>
#include <Adafruit_NeoTrellis.h>
#include <SPI.h>
#include <mcp_can.h>

#include "can_ids.h"

static const uint8_t CAN_CS_PIN = 10; // Confirm against the MCP2515 board wiring.
static const uint8_t CAN_INT_PIN = 7; // Confirm before enabling interrupt-driven receive.
static const uint32_t CAN_SPEED = CAN_500KBPS;

MCP_CAN canBus(CAN_CS_PIN);
Adafruit_NeoTrellis trellis;

bool sendButtonEvent(uint8_t buttonIndex, bool pressed) {
    uint8_t payload[BUTTON_EVENT_LENGTH] = {
        buttonIndex,
        pressed ? BUTTON_PRESSED : BUTTON_RELEASED,
    };
    return canBus.sendMsgBuf(CAN_ID_BUTTON_EVENT, 0, BUTTON_EVENT_LENGTH, payload) == CAN_OK;
}

void handleLedUpdate(const uint8_t *payload, uint8_t length) {
    if (length != LED_UPDATE_LENGTH) {
        return;
    }

    const uint8_t buttonIndex = payload[LED_UPDATE_INDEX_BYTE];
    const uint8_t colourCode = payload[LED_UPDATE_COLOUR_BYTE];

    (void)buttonIndex;
    (void)colourCode;
    // TODO: Map colour codes to NeoTrellis pixels after physical layout is confirmed.
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
    pinMode(CAN_INT_PIN, INPUT);
    Serial.begin(115200);

    if (canBus.begin(MCP_ANY, CAN_SPEED, MCP_16MHZ) == CAN_OK) {
        canBus.setMode(MCP_NORMAL);
    }

    trellis.begin();
}

void loop() {
    pollCan();
    // TODO: Add NeoTrellis key event polling after the physical layout is confirmed.
}
