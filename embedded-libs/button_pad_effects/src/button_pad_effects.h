#pragma once

#include <stdint.h>

namespace e87canbus {

constexpr uint8_t BUTTON_PAD_LED_COUNT = 16;
constexpr uint8_t BUTTON_PAD_RGB_BYTES = BUTTON_PAD_LED_COUNT * 3;
constexpr uint16_t BUTTON_PAD_TRANSFER_MAX_BYTES = 64;

struct ButtonEffectTrack {
    uint32_t started_at_ms;
    uint16_t parameter_a;
    uint16_t parameter_b;
    uint8_t rgb[3];
    uint8_t final_rgb[3];
    uint8_t kind;
    uint8_t repeat;
};

static_assert(sizeof(ButtonEffectTrack) == 16, "button effect track RAM budget changed");

class ButtonPadEffects {
   public:
    bool apply(const uint8_t *payload, uint16_t length, uint32_t now_ms);
    void render(uint32_t now_ms, uint8_t out[BUTTON_PAD_RGB_BYTES]) const;
    bool animated(uint32_t now_ms) const;
    uint16_t animationMask(uint32_t now_ms) const;
    bool committed() const;
    bool triggerRedDoubleBlink(uint8_t button_index, uint32_t now_ms);
    bool triggerDoubleBlink(uint8_t button_index, uint8_t red, uint8_t green, uint8_t blue,
                            uint32_t now_ms);
    bool setBreathe(uint8_t button_index, bool enabled);

   private:
    bool applyCommand(const uint8_t *command, uint32_t now_ms);

    ButtonEffectTrack tracks_[BUTTON_PAD_LED_COUNT] = {};
    bool program_pending_ = false;
    bool last_command_committed_ = false;
    uint16_t assigned_mask_ = 0;
    uint16_t changed_mask_ = 0;
    uint32_t blink_started_at_ms_[BUTTON_PAD_LED_COUNT] = {};
    uint8_t blink_rgb_[BUTTON_PAD_LED_COUNT][3] = {};
    uint16_t blink_mask_ = 0;
    uint16_t breathe_mask_ = 0;
};

static_assert(sizeof(ButtonPadEffects) <= 384, "button-pad renderer RAM budget changed");

}  // namespace e87canbus
