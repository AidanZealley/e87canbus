#pragma once

#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace coordinator_panel {

constexpr uint8_t PIXEL_COUNT = 5;
constexpr uint8_t MAX_CHANNEL = 127;
constexpr uint32_t FIRST_STATUS_TIMEOUT_MS = 60000;
constexpr uint32_t ESTABLISHED_STATUS_TIMEOUT_MS = 3000;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 30;
constexpr size_t MAX_LINE_LENGTH = 63;

enum class Display : uint8_t {
    STARTING,
    READY,
    HOTSPOT_WAITING,
    HOTSPOT_CONNECTED,
    FAULT,
    OFF,
};

struct Rgb {
    uint8_t red;
    uint8_t green;
    uint8_t blue;
};

inline bool parseStatus(const char *line, size_t length, Display &display) {
    struct StatusName {
        const char *name;
        Display display;
    };
    static const StatusName statuses[] = {
        {"STATUS starting", Display::STARTING},
        {"STATUS ready", Display::READY},
        {"STATUS hotspot_waiting", Display::HOTSPOT_WAITING},
        {"STATUS hotspot_connected", Display::HOTSPOT_CONNECTED},
        {"STATUS fault", Display::FAULT},
        {"STATUS off", Display::OFF},
    };
    for (const StatusName &status : statuses) {
        const size_t nameLength = strlen(status.name);
        if (length == nameLength && memcmp(line, status.name, length) == 0) {
            display = status.display;
            return true;
        }
    }
    return false;
}

class LineParser {
public:
    bool push(char byte, Display &display) {
        if (byte == '\n') {
            const bool valid = !oversized_ && parseStatus(buffer_, length_, display);
            reset();
            return valid;
        }
        if (oversized_) {
            return false;
        }
        if (length_ == MAX_LINE_LENGTH) {
            oversized_ = true;
            return false;
        }
        buffer_[length_++] = byte;
        return false;
    }

private:
    void reset() {
        length_ = 0;
        oversized_ = false;
    }

    char buffer_[MAX_LINE_LENGTH] = {};
    size_t length_ = 0;
    bool oversized_ = false;
};

class StatusTracker {
public:
    explicit StatusTracker(uint32_t bootMs) : bootMs_(bootMs) {}

    void accept(Display display, uint32_t now) {
        display_ = display;
        statusSeen_ = true;
        lastStatusMs_ = now;
        // `off` only latches against the heartbeat timeout, so a graceful shutdown does not
        // become a false fault. A later valid status still wins, which is what a coordinator
        // restart sends; otherwise the panel would stay dark until it was power-cycled.
        offLatched_ = display == Display::OFF;
    }

    Display display(uint32_t now) const {
        if (offLatched_) {
            return Display::OFF;
        }
        if (!statusSeen_) {
            return now - bootMs_ >= FIRST_STATUS_TIMEOUT_MS ? Display::FAULT
                                                             : Display::STARTING;
        }
        return now - lastStatusMs_ >= ESTABLISHED_STATUS_TIMEOUT_MS ? Display::FAULT
                                                                    : display_;
    }

private:
    uint32_t bootMs_;
    uint32_t lastStatusMs_ = 0;
    Display display_ = Display::STARTING;
    bool statusSeen_ = false;
    bool offLatched_ = false;
};

class ButtonDebouncer {
public:
    bool update(bool pressed, uint32_t now) {
        if (pressed != rawPressed_) {
            rawPressed_ = pressed;
            rawChangedMs_ = now;
        }
        if (rawPressed_ != stablePressed_ && now - rawChangedMs_ >= BUTTON_DEBOUNCE_MS) {
            stablePressed_ = rawPressed_;
            return stablePressed_;
        }
        return false;
    }

private:
    uint32_t rawChangedMs_ = 0;
    bool rawPressed_ = false;
    bool stablePressed_ = false;
};

inline Rgb bounded(uint8_t red, uint8_t green, uint8_t blue) {
    return {
        red > MAX_CHANNEL ? MAX_CHANNEL : red,
        green > MAX_CHANNEL ? MAX_CHANNEL : green,
        blue > MAX_CHANNEL ? MAX_CHANNEL : blue,
    };
}

inline void render(Display display, uint32_t now, Rgb (&pixels)[PIXEL_COUNT]) {
    for (Rgb &pixel : pixels) {
        pixel = bounded(0, 0, 0);
    }

    switch (display) {
        case Display::STARTING: {
            const uint8_t position = static_cast<uint8_t>((now / 180) % PIXEL_COUNT);
            pixels[position] = bounded(127, 127, 127);
            break;
        }
        case Display::READY:
            for (Rgb &pixel : pixels) {
                pixel = bounded(20, 20, 20);
            }
            break;
        case Display::HOTSPOT_WAITING: {
            constexpr uint16_t period = 1600;
            constexpr uint8_t minimum = 12;
            constexpr uint8_t maximum = 96;
            const uint16_t phase = static_cast<uint16_t>(now % period);
            const uint16_t ramp = phase <= period / 2 ? phase : period - phase;
            const uint8_t level = static_cast<uint8_t>(
                minimum + (static_cast<uint32_t>(maximum - minimum) * ramp) / (period / 2));
            for (Rgb &pixel : pixels) {
                pixel = bounded(0, level, level);
            }
            break;
        }
        case Display::HOTSPOT_CONNECTED:
            for (Rgb &pixel : pixels) {
                pixel = bounded(0, 127, 0);
            }
            break;
        case Display::FAULT:
            for (Rgb &pixel : pixels) {
                pixel = bounded(127, 0, 0);
            }
            break;
        case Display::OFF:
            break;
    }
}

}  // namespace coordinator_panel
