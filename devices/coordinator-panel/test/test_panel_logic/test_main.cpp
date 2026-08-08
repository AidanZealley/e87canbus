#include <limits>
#include <string>

#include "panel_logic.h"
#include <unity.h>

using namespace coordinator_panel;

namespace {

#define CHECK(...) TEST_ASSERT_TRUE((__VA_ARGS__))

LineResult feed(LineReceiver &receiver, const std::string &text, DisplayState &state) {
    LineResult result = LineResult::NONE;
    for (char value : text) {
        const LineResult next = receiver.push(value, state);
        if (next != LineResult::NONE) {
            result = next;
        }
    }
    return result;
}

void testParserAcceptsExactlySixVersionOneStates() {
    const struct {
        const char *value;
        DisplayState expected;
    } cases[] = {
        {"starting", DisplayState::STARTING},
        {"ready", DisplayState::READY},
        {"hotspot_waiting", DisplayState::HOTSPOT_WAITING},
        {"hotspot_connected", DisplayState::HOTSPOT_CONNECTED},
        {"fault", DisplayState::FAULT},
        {"off", DisplayState::OFF},
    };
    for (const auto &test : cases) {
        DisplayState state = DisplayState::FAULT;
        const std::string line = std::string("PANEL 1 STATE ") + test.value;
        CHECK(parseStateLine(line.data(), line.size(), state));
        CHECK(state == test.expected);
    }

    DisplayState unchanged = DisplayState::READY;
    CHECK(!parseStateLine("PANEL 2 STATE ready", 19, unchanged));
    CHECK(!parseStateLine("PANEL 1 STATE ready extra", 25, unchanged));
    CHECK(!parseStateLine("PANEL 1 BUTTON 1", 16, unchanged));
    CHECK(unchanged == DisplayState::READY);
}

void testReceiverBoundsAndRecovers() {
    LineReceiver receiver;
    DisplayState state = DisplayState::OFF;
    CHECK(feed(receiver, "PANEL 1 STATE ready\r\n", state) == LineResult::VALID_STATE);
    CHECK(state == DisplayState::READY);
    CHECK(feed(receiver, "PANEL 1 STATE re\rady\n", state) == LineResult::INVALID);
    CHECK(feed(receiver, "nonsense\n", state) == LineResult::INVALID);
    CHECK(feed(receiver, std::string(MAX_LINE_LENGTH + 1, 'x') + "\n", state) ==
          LineResult::OVERSIZED);
    CHECK(feed(receiver, "PANEL 1 STATE fault\n", state) == LineResult::VALID_STATE);
    CHECK(state == DisplayState::FAULT);
}

void testDebounceEmitsOnlyPressEdges() {
    ButtonDebouncer debounce;
    CHECK(!debounce.update(false, 0));
    CHECK(!debounce.update(true, 10));
    CHECK(!debounce.update(false, 20));
    CHECK(!debounce.update(true, 25));
    CHECK(!debounce.update(true, 54));
    CHECK(debounce.update(true, 55));
    CHECK(!debounce.update(true, 100));
    CHECK(!debounce.update(false, 110));
    CHECK(!debounce.update(false, 140));
    CHECK(!debounce.update(true, 150));
    CHECK(debounce.update(true, 180));
}

void testLeaseGraceTimeoutRecoveryAndOffLatch() {
    PanelState state(100);
    CHECK(state.effectiveDisplay(60099) == DisplayState::STARTING);
    CHECK(state.effectiveDisplay(60100) == DisplayState::FAULT);
    CHECK(state.helloDue(100));
    CHECK(!state.helloDue(1099));
    CHECK(state.helloDue(1100));

    state.receive(DisplayState::READY, 70000);
    CHECK(state.effectiveDisplay(71999) == DisplayState::READY);
    CHECK(state.effectiveDisplay(72000) == DisplayState::FAULT);
    CHECK(!state.canSendButton(72000));
    state.receive(DisplayState::HOTSPOT_CONNECTED, 72001);
    CHECK(state.effectiveDisplay(72001) == DisplayState::HOTSPOT_CONNECTED);
    CHECK(state.canSendButton(72001));
    CHECK(!state.helloDue(90000));

    state.receive(DisplayState::OFF, 73000);
    CHECK(state.effectiveDisplay(1000000) == DisplayState::OFF);
    CHECK(!state.canSendButton(73000));
    state.receive(DisplayState::STARTING, 1000001);
    CHECK(state.effectiveDisplay(1000001) == DisplayState::STARTING);
}

void testRenderingAndBrightness() {
    CHECK(renderPixel(DisplayState::READY, 0, 0) == Rgb{77, 77, 77});
    CHECK(renderPixel(DisplayState::HOTSPOT_CONNECTED, 0, 0) == Rgb{16, 185, 129});
    CHECK(renderPixel(DisplayState::FAULT, 0, 0) == Rgb{239, 68, 68});
    CHECK(renderPixel(DisplayState::OFF, 0, 0) == Rgb{0, 0, 0});
    CHECK(renderPixel(DisplayState::READY, PIXEL_COUNT, 0) == Rgb{0, 0, 0});

    const Rgb travelLow = renderPixel(DisplayState::STARTING, 0, 0);
    const Rgb travelPeak = renderPixel(DisplayState::STARTING, 0, 420);
    CHECK(travelPeak.red > travelLow.red);
    CHECK(renderPixel(DisplayState::STARTING, 1, STARTUP_STAGGER_MS) == travelLow);
    CHECK(renderPixel(DisplayState::STARTING, 1, 420 + STARTUP_STAGGER_MS) == travelPeak);
    CHECK(renderPixel(DisplayState::STARTING, 0, STARTUP_CYCLE_MS) == travelLow);

    const Rgb pulseLow = renderPixel(DisplayState::HOTSPOT_WAITING, 0, 0);
    const Rgb pulseHigh = renderPixel(DisplayState::HOTSPOT_WAITING, 0, 900);
    CHECK(pulseLow.green < pulseHigh.green);
    CHECK(pulseHigh.green == pulseHigh.blue);
    CHECK(renderPixel(DisplayState::HOTSPOT_WAITING, 0, HOTSPOT_PULSE_CYCLE_MS) == pulseLow);
    CHECK(applyBrightnessCeiling({255, 128, 0}, 48) == Rgb{48, 24, 0});
}

void testSequenceWraps() {
    ButtonSequence sequence(std::numeric_limits<uint32_t>::max() - 1);
    CHECK(sequence.next() == std::numeric_limits<uint32_t>::max());
    CHECK(sequence.next() == 0);
    CHECK(sequence.next() == 1);
}

}  // namespace

void setUp() {}
void tearDown() {}

int main() {
    UNITY_BEGIN();
    RUN_TEST(testParserAcceptsExactlySixVersionOneStates);
    RUN_TEST(testReceiverBoundsAndRecovers);
    RUN_TEST(testDebounceEmitsOnlyPressEdges);
    RUN_TEST(testLeaseGraceTimeoutRecoveryAndOffLatch);
    RUN_TEST(testRenderingAndBrightness);
    RUN_TEST(testSequenceWraps);
    return UNITY_END();
}
