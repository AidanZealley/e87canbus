#include "button_pad_effects.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <vector>

#include "button_pad_vectors.generated.h"

namespace {

int fail(const char *program, const char *message, uint32_t elapsed_ms = 0) {
    fprintf(stderr, "%s: %s at %lu ms\n", program, message,
            static_cast<unsigned long>(elapsed_ms));
    return 1;
}

}  // namespace

int main() {
    constexpr uint32_t STARTED_AT_MS = 0xFFFFFF00UL;

    for (const auto &vector : VALID_PROGRAMS) {
        e87canbus::ButtonPadEffects effects;
        for (size_t index = 0; index < vector.commands.size(); ++index) {
            const auto &command = vector.commands[index];
            if (!effects.apply(command.data(), command.size(), STARTED_AT_MS)) {
                return fail(vector.name, "valid command was rejected");
            }
            if (effects.committed() != (index == vector.commands.size() - 1)) {
                return fail(vector.name, "program committed before its final command");
            }
        }
        for (const auto &frame : vector.frames) {
            const uint32_t now = STARTED_AT_MS + frame.elapsed_ms;
            if (effects.animationMask(now) != frame.animation_mask ||
                effects.animated(now) != (frame.animation_mask != 0)) {
                return fail(vector.name, "animation mask differed", frame.elapsed_ms);
            }
            uint8_t rendered[e87canbus::BUTTON_PAD_RGB_BYTES] = {};
            effects.render(now, rendered);
            if (memcmp(rendered, frame.rgb.data(), sizeof(rendered)) != 0) {
                return fail(vector.name, "rendered frame differed", frame.elapsed_ms);
            }
        }
    }

    // Replacing one button must not restart an unchanged effect on another button.
    {
        e87canbus::ButtonPadEffects effects;
        const auto &program = VALID_PROGRAMS.front();
        for (const auto &command : program.commands) {
            if (!effects.apply(command.data(), command.size(), STARTED_AT_MS)) {
                return fail("continuity", "initial command was rejected");
            }
        }
        auto updated = program.commands;
        updated.front()[5] = 0x20;
        for (const auto &command : updated) {
            if (!effects.apply(command.data(), command.size(), STARTED_AT_MS + 400)) {
                return fail("continuity", "updated command was rejected");
            }
        }
        uint8_t rendered[e87canbus::BUTTON_PAD_RGB_BYTES] = {};
        effects.render(STARTED_AT_MS + 800, rendered);
        const auto &expected = program.frames[2].rgb;
        if (memcmp(rendered + 45, expected.data() + 45, 3) != 0) {
            return fail("continuity", "unchanged effect restarted", 800);
        }
    }

    // Packing up to four command records into a single transfer must render
    // identically to delivering the same records one per transfer.
    constexpr size_t RECORDS_PER_TRANSFER = 4;
    for (const auto &vector : VALID_PROGRAMS) {
        e87canbus::ButtonPadEffects effects;
        for (size_t start = 0; start < vector.commands.size(); start += RECORDS_PER_TRANSFER) {
            std::vector<uint8_t> transfer;
            for (size_t index = start;
                 index < vector.commands.size() && index < start + RECORDS_PER_TRANSFER; ++index) {
                transfer.insert(transfer.end(), vector.commands[index].begin(),
                                vector.commands[index].end());
            }
            if (!effects.apply(transfer.data(), static_cast<uint16_t>(transfer.size()),
                               STARTED_AT_MS)) {
                return fail(vector.name, "packed transfer was rejected");
            }
        }
        for (const auto &frame : vector.frames) {
            const uint32_t now = STARTED_AT_MS + frame.elapsed_ms;
            uint8_t rendered[e87canbus::BUTTON_PAD_RGB_BYTES] = {};
            effects.render(now, rendered);
            if (memcmp(rendered, frame.rgb.data(), sizeof(rendered)) != 0) {
                return fail(vector.name, "packed transfer rendered differently", frame.elapsed_ms);
            }
        }
    }

    for (const auto &vector : INVALID_PROGRAMS) {
        e87canbus::ButtonPadEffects effects;
        if (effects.apply(vector.payload.data(), vector.payload.size(), STARTED_AT_MS)) {
            return fail(vector.name, "invalid program was accepted");
        }
        if (effects.animationMask(STARTED_AT_MS) != 0 || effects.animated(STARTED_AT_MS)) {
            return fail(vector.name, "rejected program became animated");
        }
    }
    return 0;
}
