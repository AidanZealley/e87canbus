#include <unity.h>

#include "panel_logic.h"

using namespace coordinator_panel;

void test_parser_accepts_only_complete_bounded_status_lines() {
    LineParser parser;
    Display display = Display::OFF;
    const char valid[] = "STATUS hotspot_connected\n";
    for (size_t index = 0; index < sizeof(valid) - 2; ++index) {
        TEST_ASSERT_FALSE(parser.push(valid[index], display));
    }
    TEST_ASSERT_TRUE(parser.push('\n', display));
    TEST_ASSERT_EQUAL(Display::HOTSPOT_CONNECTED, display);

    const char malformed[] = "STATUS connected\n";
    for (char byte : malformed) {
        TEST_ASSERT_FALSE(parser.push(byte, display));
    }

    for (size_t index = 0; index < MAX_LINE_LENGTH + 1; ++index) {
        TEST_ASSERT_FALSE(parser.push('x', display));
    }
    TEST_ASSERT_FALSE(parser.push('\n', display));
    const char recovery[] = "STATUS ready\n";
    bool accepted = false;
    for (char byte : recovery) {
        accepted = parser.push(byte, display) || accepted;
    }
    TEST_ASSERT_TRUE(accepted);
    TEST_ASSERT_EQUAL(Display::READY, display);
}

void test_status_timeouts_recover_and_off_latches() {
    StatusTracker status(100);
    TEST_ASSERT_EQUAL(Display::STARTING, status.display(60099));
    TEST_ASSERT_EQUAL(Display::FAULT, status.display(60100));
    status.accept(Display::READY, 70000);
    TEST_ASSERT_EQUAL(Display::READY, status.display(72999));
    TEST_ASSERT_EQUAL(Display::FAULT, status.display(73000));
    status.accept(Display::HOTSPOT_CONNECTED, 74000);
    TEST_ASSERT_EQUAL(Display::HOTSPOT_CONNECTED, status.display(74000));
    status.accept(Display::OFF, 75000);
    TEST_ASSERT_EQUAL(Display::OFF, status.display(200000));
    status.accept(Display::FAULT, 200001);
    TEST_ASSERT_EQUAL(Display::OFF, status.display(200001));
}

void test_button_emits_once_per_debounced_press() {
    ButtonDebouncer button;
    TEST_ASSERT_FALSE(button.update(true, 10));
    TEST_ASSERT_FALSE(button.update(false, 20));
    TEST_ASSERT_FALSE(button.update(true, 25));
    TEST_ASSERT_FALSE(button.update(true, 54));
    TEST_ASSERT_TRUE(button.update(true, 55));
    TEST_ASSERT_FALSE(button.update(true, 100));
    TEST_ASSERT_FALSE(button.update(false, 110));
    TEST_ASSERT_FALSE(button.update(false, 140));
    TEST_ASSERT_FALSE(button.update(true, 150));
    TEST_ASSERT_TRUE(button.update(true, 180));
}

void test_rendering_has_six_semantics_and_hard_channel_cap() {
    Rgb pixels[PIXEL_COUNT];
    const Display displays[] = {Display::STARTING, Display::READY, Display::HOTSPOT_WAITING,
                                Display::HOTSPOT_CONNECTED, Display::FAULT, Display::OFF};
    for (Display display : displays) {
        render(display, 400, pixels);
        for (const Rgb &pixel : pixels) {
            TEST_ASSERT_LESS_OR_EQUAL_UINT8(MAX_CHANNEL, pixel.red);
            TEST_ASSERT_LESS_OR_EQUAL_UINT8(MAX_CHANNEL, pixel.green);
            TEST_ASSERT_LESS_OR_EQUAL_UINT8(MAX_CHANNEL, pixel.blue);
        }
    }

    render(Display::READY, 0, pixels);
    TEST_ASSERT_TRUE(pixels[0].red > 0 && pixels[0].red == pixels[0].green &&
                     pixels[0].green == pixels[0].blue);
    render(Display::HOTSPOT_WAITING, 400, pixels);
    TEST_ASSERT_TRUE(pixels[0].red == 0 && pixels[0].green == pixels[0].blue &&
                     pixels[0].blue > 0);
    render(Display::HOTSPOT_CONNECTED, 0, pixels);
    TEST_ASSERT_TRUE(pixels[0].red == 0 && pixels[0].green > 0 && pixels[0].blue == 0);
    render(Display::FAULT, 0, pixels);
    TEST_ASSERT_TRUE(pixels[0].red > 0 && pixels[0].green == 0 && pixels[0].blue == 0);
    render(Display::OFF, 0, pixels);
    TEST_ASSERT_TRUE(pixels[0].red == 0 && pixels[0].green == 0 && pixels[0].blue == 0);
}

int main(int, char **) {
    UNITY_BEGIN();
    RUN_TEST(test_parser_accepts_only_complete_bounded_status_lines);
    RUN_TEST(test_status_timeouts_recover_and_off_latches);
    RUN_TEST(test_button_emits_once_per_debounced_press);
    RUN_TEST(test_rendering_has_six_semantics_and_hard_channel_cap);
    return UNITY_END();
}
