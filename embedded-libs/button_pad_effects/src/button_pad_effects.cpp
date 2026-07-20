#include "button_pad_effects.h"

#include <string.h>

namespace {

constexpr uint8_t PROGRAM_VERSION = 2;
constexpr uint8_t REPLACE_ALL = 1;
constexpr uint8_t SET_TRACK = 2;
constexpr uint8_t COMMIT = 0x80;
constexpr uint8_t SOLID = 1;
constexpr uint8_t BLINK = 2;
constexpr uint8_t BREATHE = 3;
constexpr uint16_t COMMAND_LENGTH = 16;

uint16_t littleEndian16(const uint8_t *bytes) {
    return static_cast<uint16_t>(bytes[0]) | (static_cast<uint16_t>(bytes[1]) << 8);
}

bool trackValid(uint8_t kind, uint16_t parameterA, uint16_t parameterB, uint8_t repeat) {
    if (kind == SOLID) {
        return parameterA == 0 && parameterB == 0 && repeat == 0;
    }
    if (kind == BLINK) {
        return parameterA >= 1 && parameterA <= 10000 && parameterB >= 1 &&
               parameterB <= 10000;
    }
    if (kind == BREATHE) {
        const uint8_t minimum = parameterB & 0xFF;
        const uint8_t maximum = parameterB >> 8;
        return parameterA >= 250 && parameterA <= 10000 && minimum <= maximum;
    }
    return false;
}

uint32_t cycleDuration(const e87canbus::ButtonEffectTrack &track) {
    return track.kind == BLINK ? static_cast<uint32_t>(track.parameter_a) + track.parameter_b
                               : track.parameter_a;
}

bool complete(const e87canbus::ButtonEffectTrack &track, uint32_t nowMs) {
    return track.kind != SOLID && track.repeat != 0 &&
           nowMs - track.started_at_ms >= cycleDuration(track) * track.repeat;
}

bool sameEffect(const e87canbus::ButtonEffectTrack &left,
                const e87canbus::ButtonEffectTrack &right) {
    return left.parameter_a == right.parameter_a && left.parameter_b == right.parameter_b &&
           memcmp(left.rgb, right.rgb, 3) == 0 &&
           memcmp(left.final_rgb, right.final_rgb, 3) == 0 && left.kind == right.kind &&
           left.repeat == right.repeat;
}

}  // namespace

namespace e87canbus {

bool ButtonPadEffects::apply(const uint8_t *payload, uint16_t length, uint32_t now_ms) {
    last_command_committed_ = false;
    if (payload == nullptr || length == 0 || length % COMMAND_LENGTH != 0 ||
        length > BUTTON_PAD_TRANSFER_MAX_BYTES) {
        return false;
    }
    for (uint16_t offset = 0; offset < length; offset += COMMAND_LENGTH) {
        if (!applyCommand(payload + offset, now_ms)) {
            return false;
        }
    }
    return true;
}

bool ButtonPadEffects::applyCommand(const uint8_t *command, uint32_t now_ms) {
    const uint8_t opcode = command[1] & ~COMMIT;
    if (command[0] != PROGRAM_VERSION || (opcode != REPLACE_ALL && opcode != SET_TRACK)) {
        return false;
    }
    const uint16_t targetMask = littleEndian16(command + 2);
    const uint8_t kind = command[4];
    const uint16_t parameterA = littleEndian16(command + 8);
    const uint16_t parameterB = littleEndian16(command + 10);
    const uint8_t repeat = command[12];
    if (targetMask == 0 || !trackValid(kind, parameterA, parameterB, repeat)) {
        return false;
    }
    if (opcode == SET_TRACK && !program_pending_) {
        return false;
    }
    if (opcode == REPLACE_ALL) {
        program_pending_ = true;
        assigned_mask_ = 0;
        changed_mask_ = 0;
    }
    if (assigned_mask_ & targetMask) {
        return false;
    }

    ButtonEffectTrack track{};
    track.started_at_ms = 0;
    track.parameter_a = parameterA;
    track.parameter_b = parameterB;
    memcpy(track.rgb, command + 5, 3);
    memcpy(track.final_rgb, command + 13, 3);
    track.kind = kind;
    track.repeat = repeat;
    for (uint8_t index = 0; index < BUTTON_PAD_LED_COUNT; ++index) {
        if (targetMask & (1U << index)) {
            ButtonEffectTrack replacement = track;
            replacement.started_at_ms = tracks_[index].started_at_ms;
            if (!sameEffect(tracks_[index], track)) {
                changed_mask_ |= 1U << index;
                replacement.started_at_ms = 0;
            }
            tracks_[index] = replacement;
        }
    }
    assigned_mask_ |= targetMask;
    if (command[1] & COMMIT) {
        if (assigned_mask_ != 0xFFFF) {
            return false;
        }
        for (uint8_t index = 0; index < BUTTON_PAD_LED_COUNT; ++index) {
            if (changed_mask_ & (1U << index)) {
                tracks_[index].started_at_ms = now_ms;
            }
        }
        program_pending_ = false;
        last_command_committed_ = true;
    }
    return true;
}

void ButtonPadEffects::render(uint32_t now_ms, uint8_t out[BUTTON_PAD_RGB_BYTES]) const {
    for (uint8_t index = 0; index < BUTTON_PAD_LED_COUNT; ++index) {
        const ButtonEffectTrack &track = tracks_[index];
        uint8_t *rgb = out + index * 3;
        if (complete(track, now_ms)) {
            memcpy(rgb, track.final_rgb, 3);
            continue;
        }
        if (track.kind == SOLID) {
            memcpy(rgb, track.rgb, 3);
            continue;
        }
        if (track.kind != BLINK && track.kind != BREATHE) {
            memset(rgb, 0, 3);
            continue;
        }
        const uint32_t elapsed = now_ms - track.started_at_ms;
        if (track.kind == BLINK) {
            const uint32_t phase = elapsed % cycleDuration(track);
            if (phase < track.parameter_a) {
                memcpy(rgb, track.rgb, 3);
            } else {
                memcpy(rgb, track.final_rgb, 3);
            }
            continue;
        }
        const uint32_t phase = elapsed % track.parameter_a;
        const uint16_t halfPeriod = track.parameter_a / 2;
        const uint16_t triangle =
            phase <= halfPeriod
                ? static_cast<uint16_t>((phase * 255UL) / halfPeriod)
                : static_cast<uint16_t>(((track.parameter_a - phase) * 255UL) /
                                        (track.parameter_a - halfPeriod));
        const uint8_t minimum = track.parameter_b & 0xFF;
        const uint8_t maximum = track.parameter_b >> 8;
        const uint16_t brightness = minimum + ((maximum - minimum) * triangle) / 255;
        for (uint8_t channel = 0; channel < 3; ++channel) {
            rgb[channel] = static_cast<uint8_t>((track.rgb[channel] * brightness) / 255);
        }
    }
}

uint16_t ButtonPadEffects::animationMask(uint32_t now_ms) const {
    if (program_pending_) {
        return 0;
    }
    uint16_t mask = 0;
    for (uint8_t index = 0; index < BUTTON_PAD_LED_COUNT; ++index) {
        if ((tracks_[index].kind == BLINK || tracks_[index].kind == BREATHE) &&
            !complete(tracks_[index], now_ms)) {
            mask |= 1U << index;
        }
    }
    return mask;
}

bool ButtonPadEffects::animated(uint32_t now_ms) const { return animationMask(now_ms) != 0; }

bool ButtonPadEffects::committed() const { return last_command_committed_; }

}  // namespace e87canbus
