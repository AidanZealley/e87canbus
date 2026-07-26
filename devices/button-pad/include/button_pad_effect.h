#pragma once

#include <stdint.h>

#include "can_ids.h"

namespace button_pad {

/// What an incremental effect frame asks the pad to do.
///
/// The pad implements exactly one- and two-pulse blinks, so the pulse count in the
/// frame is a choice between two entry points rather than a free parameter.
enum class EffectAction : uint8_t {
    IGNORE,
    SINGLE_BLINK,
    DOUBLE_BLINK,
};

struct EffectCommand {
    EffectAction action;
    uint8_t buttonIndex;
    uint8_t red;
    uint8_t green;
    uint8_t blue;
};

/// Decide what a ``0x701`` frame means, with no hardware or device state involved.
///
/// Anything the pad cannot render — a foreign command version, an unknown opcode, a
/// button outside the pad, or a pulse count with no entry point — decodes to
/// ``IGNORE`` rather than to a partially populated command, so a caller has exactly
/// one branch to check before acting. Version 2 is required because version 1 gave
/// bytes 4-7 an entirely different meaning; accepting it would render a black blink.
inline EffectCommand decodeEffectCommand(const uint8_t *payload, uint8_t length,
                                         uint8_t buttonCount) {
    EffectCommand command = {EffectAction::IGNORE, 0, 0, 0, 0};
    if (length != BUTTON_PAD_EFFECT_LENGTH ||
        payload[BUTTON_PAD_EFFECT_VERSION_BYTE] != BUTTON_PAD_EFFECT_COMMAND_VERSION ||
        payload[BUTTON_PAD_EFFECT_OPCODE_BYTE] != BUTTON_PAD_EFFECT_BLINK ||
        payload[BUTTON_PAD_EFFECT_BUTTON_INDEX_BYTE] >= buttonCount) {
        return command;
    }
    const uint8_t pulses = payload[BUTTON_PAD_EFFECT_PULSES_BYTE];
    if (pulses == 1) {
        command.action = EffectAction::SINGLE_BLINK;
    } else if (pulses == 2) {
        command.action = EffectAction::DOUBLE_BLINK;
    } else {
        return command;
    }
    command.buttonIndex = payload[BUTTON_PAD_EFFECT_BUTTON_INDEX_BYTE];
    command.red = payload[BUTTON_PAD_EFFECT_RED_BYTE];
    command.green = payload[BUTTON_PAD_EFFECT_GREEN_BYTE];
    command.blue = payload[BUTTON_PAD_EFFECT_BLUE_BYTE];
    return command;
}

}  // namespace button_pad
