#include "panel_logic.h"

#include <string.h>

namespace coordinator_panel {
namespace {

constexpr char PREFIX[] = "PANEL 1 STATE ";

bool equals(const char *line, size_t length, const char *expected) {
    const size_t expectedLength = strlen(expected);
    return length == expectedLength && memcmp(line, expected, length) == 0;
}

uint8_t lerp(uint8_t from, uint8_t to, uint16_t progress, uint16_t total) {
    return static_cast<uint8_t>(
        from + (static_cast<uint32_t>(to - from) * progress) / total);
}

// Integer smoothstep gives the animations an ease-in-out shape without floating point.
uint16_t smooth(uint16_t progress, uint16_t total) {
    const uint32_t x = (static_cast<uint32_t>(progress) * 1024U) / total;
    return static_cast<uint16_t>((x * x * (3072U - 2U * x)) / (1024U * 1024U));
}

uint8_t easedRamp(uint8_t from, uint8_t to, uint16_t progress, uint16_t total) {
    return lerp(from, to, smooth(progress, total), 1024);
}

uint8_t startupLevel(uint32_t phase) {
    constexpr uint16_t PEAK_MS = 420;  // 30% of the accepted 1.4 s cycle.
    constexpr uint16_t FADE_END_MS = 840;
    constexpr uint8_t LOW = 46;   // Browser opacity 0.18.
    constexpr uint8_t HIGH = 230; // Browser opacity 0.90.
    if (phase < PEAK_MS) {
        return easedRamp(LOW, HIGH, static_cast<uint16_t>(phase), PEAK_MS);
    }
    if (phase < FADE_END_MS) {
        return easedRamp(LOW, HIGH, static_cast<uint16_t>(FADE_END_MS - phase), PEAK_MS);
    }
    return LOW;
}

uint8_t pulseLevel(uint32_t phase) {
    constexpr uint16_t HALF_CYCLE_MS = HOTSPOT_PULSE_CYCLE_MS / 2;
    constexpr uint8_t LOW = 77;   // Browser opacity 0.30.
    constexpr uint8_t HIGH = 217; // Browser opacity 0.85.
    const uint16_t progress = phase < HALF_CYCLE_MS
                                  ? static_cast<uint16_t>(phase)
                                  : static_cast<uint16_t>(HOTSPOT_PULSE_CYCLE_MS - phase);
    return easedRamp(LOW, HIGH, progress, HALF_CYCLE_MS);
}

}  // namespace

bool parseStateLine(const char *line, size_t length, DisplayState &state) {
    const size_t prefixLength = sizeof(PREFIX) - 1;
    if (length <= prefixLength || memcmp(line, PREFIX, prefixLength) != 0) {
        return false;
    }
    const char *value = line + prefixLength;
    const size_t valueLength = length - prefixLength;
    if (equals(value, valueLength, "starting")) {
        state = DisplayState::STARTING;
    } else if (equals(value, valueLength, "ready")) {
        state = DisplayState::READY;
    } else if (equals(value, valueLength, "hotspot_waiting")) {
        state = DisplayState::HOTSPOT_WAITING;
    } else if (equals(value, valueLength, "hotspot_connected")) {
        state = DisplayState::HOTSPOT_CONNECTED;
    } else if (equals(value, valueLength, "fault")) {
        state = DisplayState::FAULT;
    } else if (equals(value, valueLength, "off")) {
        state = DisplayState::OFF;
    } else {
        return false;
    }
    return true;
}

LineResult LineReceiver::push(char value, DisplayState &state) {
    if (value != '\n') {
        if (discarding_) {
            return LineResult::NONE;
        }
        if (length_ == MAX_LINE_LENGTH) {
            length_ = 0;
            discarding_ = true;
            return LineResult::NONE;
        }
        buffer_[length_++] = value;
        return LineResult::NONE;
    }

    if (discarding_) {
        discarding_ = false;
        return LineResult::OVERSIZED;
    }
    // Accept conventional CRLF, while preserving an embedded carriage return as malformed input.
    const size_t lineLength = length_ > 0 && buffer_[length_ - 1] == '\r' ? length_ - 1 : length_;
    const bool valid = parseStateLine(buffer_, lineLength, state);
    length_ = 0;
    return valid ? LineResult::VALID_STATE : LineResult::INVALID;
}

bool ButtonDebouncer::update(bool pressed, uint32_t nowMs) {
    if (!initialized_) {
        candidatePressed_ = pressed;
        stablePressed_ = pressed;
        candidateSinceMs_ = nowMs;
        initialized_ = true;
        return false;
    }
    if (pressed != candidatePressed_) {
        candidatePressed_ = pressed;
        candidateSinceMs_ = nowMs;
        return false;
    }
    if (candidatePressed_ == stablePressed_ || nowMs - candidateSinceMs_ < BUTTON_DEBOUNCE_MS) {
        return false;
    }
    stablePressed_ = candidatePressed_;
    return stablePressed_;
}

uint32_t ButtonSequence::next() {
    ++previous_; // Unsigned wrap is the protocol's intended modulo-2^32 behavior.
    return previous_;
}

void PanelState::receive(DisplayState state, uint32_t nowMs) {
    if (!established_ || state != commanded_) {
        stateSinceMs_ = nowMs;
    }
    commanded_ = state;
    lastStateMs_ = nowMs;
    established_ = true;
}

bool PanelState::heartbeatExpired(uint32_t nowMs) const {
    return established_ && commanded_ != DisplayState::OFF &&
           nowMs - lastStateMs_ >= HEARTBEAT_TIMEOUT_MS;
}

DisplayState PanelState::effectiveDisplay(uint32_t nowMs) const {
    if (!established_) {
        return nowMs - bootMs_ >= INITIAL_STATE_GRACE_MS ? DisplayState::FAULT
                                                         : DisplayState::STARTING;
    }
    return heartbeatExpired(nowMs) ? DisplayState::FAULT : commanded_;
}

bool PanelState::canSendButton(uint32_t nowMs) const {
    return established_ && commanded_ != DisplayState::OFF && !heartbeatExpired(nowMs);
}

bool PanelState::helloDue(uint32_t nowMs) {
    if (established_ || static_cast<int32_t>(nowMs - nextHelloMs_) < 0) {
        return false;
    }
    nextHelloMs_ = nowMs + HELLO_INTERVAL_MS;
    return true;
}

Rgb renderPixel(DisplayState state, uint8_t pixel, uint32_t elapsedMs) {
    if (pixel >= PIXEL_COUNT) {
        return {0, 0, 0};
    }
    switch (state) {
        case DisplayState::STARTING: {
            const uint32_t offset = static_cast<uint32_t>(pixel) * STARTUP_STAGGER_MS;
            const uint8_t level = startupLevel(
                (elapsedMs + STARTUP_CYCLE_MS - offset % STARTUP_CYCLE_MS) % STARTUP_CYCLE_MS);
            return {level, level, level};
        }
        case DisplayState::READY:
            return {77, 77, 77};
        case DisplayState::HOTSPOT_WAITING: {
            const uint8_t level = pulseLevel(elapsedMs % HOTSPOT_PULSE_CYCLE_MS);
            return {0, level, level};
        }
        case DisplayState::HOTSPOT_CONNECTED:
            return {16, 185, 129};
        case DisplayState::FAULT:
            return {239, 68, 68};
        case DisplayState::OFF:
            return {0, 0, 0};
    }
    return {0, 0, 0};
}

Rgb applyBrightnessCeiling(Rgb colour, uint8_t ceiling) {
    const auto scale = [ceiling](uint8_t channel) {
        return static_cast<uint8_t>((static_cast<uint16_t>(channel) * ceiling + 127U) / 255U);
    };
    return {scale(colour.red), scale(colour.green), scale(colour.blue)};
}

}  // namespace coordinator_panel
