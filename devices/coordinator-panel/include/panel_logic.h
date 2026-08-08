#pragma once

#include <stddef.h>
#include <stdint.h>

namespace coordinator_panel {

constexpr uint8_t PIXEL_COUNT = 5;
constexpr size_t MAX_LINE_LENGTH = 63;
constexpr uint32_t HELLO_INTERVAL_MS = 1000;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 30;
constexpr uint32_t INITIAL_STATE_GRACE_MS = 60000;
constexpr uint32_t HEARTBEAT_TIMEOUT_MS = 2000;
constexpr uint32_t STARTUP_CYCLE_MS = 1400;
constexpr uint32_t STARTUP_STAGGER_MS = 140;
constexpr uint32_t HOTSPOT_PULSE_CYCLE_MS = 1800;

enum class DisplayState : uint8_t {
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

    bool operator==(const Rgb &other) const {
        return red == other.red && green == other.green && blue == other.blue;
    }
};

enum class LineResult : uint8_t {
    NONE,
    VALID_STATE,
    INVALID,
    OVERSIZED,
};

bool parseStateLine(const char *line, size_t length, DisplayState &state);

/// Bounded UART framing. Once a line overflows it is discarded through its newline.
class LineReceiver {
  public:
    LineResult push(char value, DisplayState &state);

  private:
    char buffer_[MAX_LINE_LENGTH + 1] = {};
    size_t length_ = 0;
    bool discarding_ = false;
};

/// Emits only a stable transition from released to pressed.
class ButtonDebouncer {
  public:
    bool update(bool pressed, uint32_t nowMs);

  private:
    bool candidatePressed_ = false;
    bool stablePressed_ = false;
    uint32_t candidateSinceMs_ = 0;
    bool initialized_ = false;
};

class ButtonSequence {
  public:
    explicit ButtonSequence(uint32_t previous = 0) : previous_(previous) {}
    uint32_t next();

  private:
    uint32_t previous_;
};

/// Tracks the Pi lease independently of rendering and UART I/O.
class PanelState {
  public:
    explicit PanelState(uint32_t bootMs = 0) : bootMs_(bootMs), stateSinceMs_(bootMs) {}

    void receive(DisplayState state, uint32_t nowMs);
    DisplayState effectiveDisplay(uint32_t nowMs) const;
    bool canSendButton(uint32_t nowMs) const;
    bool helloDue(uint32_t nowMs);
    uint32_t animationSinceMs() const { return stateSinceMs_; }

  private:
    bool heartbeatExpired(uint32_t nowMs) const;

    uint32_t bootMs_;
    uint32_t stateSinceMs_;
    uint32_t lastStateMs_ = 0;
    uint32_t nextHelloMs_ = 0;
    DisplayState commanded_ = DisplayState::STARTING;
    bool established_ = false;
};

Rgb renderPixel(DisplayState state, uint8_t pixel, uint32_t elapsedMs);
Rgb applyBrightnessCeiling(Rgb colour, uint8_t ceiling);

}  // namespace coordinator_panel
