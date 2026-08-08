#include <Adafruit_NeoPixel.h>
#include <Arduino.h>

#include "panel_logic.h"

namespace {

using coordinator_panel::ButtonDebouncer;
using coordinator_panel::ButtonSequence;
using coordinator_panel::DisplayState;
using coordinator_panel::LineReceiver;
using coordinator_panel::LineResult;
using coordinator_panel::PanelState;

constexpr uint32_t UART_BAUD = 115200;
constexpr uint32_t FRAME_INTERVAL_MS = 20;
constexpr uint8_t PIXEL_PIN = A3;
constexpr uint8_t BUTTON_PIN = A0;
// Scale every colour before it reaches the strip, limiting both glare and current.
constexpr uint8_t BRIGHTNESS_CEILING = 48;

Adafruit_NeoPixel pixels(coordinator_panel::PIXEL_COUNT, PIXEL_PIN, NEO_GRB + NEO_KHZ800);
LineReceiver receiver;
ButtonDebouncer button;
ButtonSequence buttonSequence;
PanelState panel;
uint32_t nextFrameMs = 0;

bool due(uint32_t nowMs, uint32_t deadlineMs) {
    return static_cast<int32_t>(nowMs - deadlineMs) >= 0;
}

void render(uint32_t nowMs) {
    const DisplayState state = panel.effectiveDisplay(nowMs);
    const uint32_t elapsedMs = nowMs - panel.animationSinceMs();
    for (uint8_t index = 0; index < coordinator_panel::PIXEL_COUNT; ++index) {
        const auto colour = coordinator_panel::applyBrightnessCeiling(
            coordinator_panel::renderPixel(state, index, elapsedMs), BRIGHTNESS_CEILING);
        pixels.setPixelColor(index, pixels.Color(colour.red, colour.green, colour.blue));
    }
    pixels.show();
}

void receiveStates(uint32_t nowMs) {
    while (Serial2.available() > 0) {
        DisplayState state;
        if (receiver.push(static_cast<char>(Serial2.read()), state) == LineResult::VALID_STATE) {
            panel.receive(state, nowMs);
        }
    }
}

void sendButtonIfPressed(uint32_t nowMs) {
    const bool pressed = digitalRead(BUTTON_PIN) == LOW;
    if (!button.update(pressed, nowMs) || !panel.canSendButton(nowMs)) {
        return;
    }
    Serial2.print("PANEL 1 BUTTON ");
    Serial2.println(buttonSequence.next());
}

}  // namespace

void setup() {
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pixels.begin();
    pixels.clear();
    pixels.show();
    // On the QT Py variant Serial2 is routed to the pads labelled TX and RX.
    Serial2.begin(UART_BAUD);
    panel = PanelState(millis());
    render(millis());
}

void loop() {
    const uint32_t nowMs = millis();
    receiveStates(nowMs);
    if (panel.helloDue(nowMs)) {
        Serial2.println("PANEL 1 HELLO");
    }
    sendButtonIfPressed(nowMs);
    if (due(nowMs, nextFrameMs)) {
        render(nowMs);
        nextFrameMs = nowMs + FRAME_INTERVAL_MS;
    }
}
