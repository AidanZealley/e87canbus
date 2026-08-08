#include <Adafruit_NeoPixel.h>
#include <Arduino.h>

#include "panel_logic.h"

namespace {

constexpr uint32_t UART_BAUD = 115200;
constexpr uint32_t FRAME_INTERVAL_MS = 20;
constexpr uint8_t BUTTON_PIN = A0;
constexpr uint8_t PIXEL_PIN = A3;

using coordinator_panel::ButtonDebouncer;
using coordinator_panel::Display;
using coordinator_panel::LineParser;
using coordinator_panel::PIXEL_COUNT;
using coordinator_panel::Rgb;
using coordinator_panel::StatusTracker;

Adafruit_NeoPixel strip(PIXEL_COUNT, PIXEL_PIN, NEO_GRB + NEO_KHZ800);
LineParser parser;
ButtonDebouncer button;
StatusTracker status(0);
uint32_t nextFrameMs = 0;

void show(Display display, uint32_t now) {
    Rgb pixels[PIXEL_COUNT];
    coordinator_panel::render(display, now, pixels);
    for (uint8_t index = 0; index < PIXEL_COUNT; ++index) {
        strip.setPixelColor(index, pixels[index].red, pixels[index].green, pixels[index].blue);
    }
    strip.show();
}

}  // namespace

void setup() {
    const uint32_t now = millis();
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    strip.begin();
    show(Display::STARTING, now);

    Serial2.setTX(PIN_SERIAL2_TX);
    Serial2.setRX(PIN_SERIAL2_RX);
    Serial2.begin(UART_BAUD);
}

void loop() {
    const uint32_t now = millis();

    while (Serial2.available() > 0) {
        Display received;
        if (parser.push(static_cast<char>(Serial2.read()), received)) {
            status.accept(received, now);
        }
    }

    if (button.update(digitalRead(BUTTON_PIN) == LOW, now)) {
        Serial2.print("BUTTON\n");
    }

    if (static_cast<int32_t>(now - nextFrameMs) >= 0) {
        show(status.display(now), now);
        nextFrameMs = now + FRAME_INTERVAL_MS;
    }
}
