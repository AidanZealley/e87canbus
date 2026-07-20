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

   private:
    bool applyCommand(const uint8_t *command, uint32_t now_ms);

    ButtonEffectTrack tracks_[BUTTON_PAD_LED_COUNT] = {};
    bool program_pending_ = false;
    bool last_command_committed_ = false;
    uint16_t assigned_mask_ = 0;
    uint16_t changed_mask_ = 0;
};

static_assert(sizeof(ButtonPadEffects) <= 264, "button-pad renderer RAM budget changed");

}  // namespace e87canbus
