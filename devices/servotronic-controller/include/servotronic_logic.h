#pragma once

#include <stdint.h>

namespace servotronic {

constexpr uint32_t SPEED_CAN_ID = 0x1FFFFF00UL;
constexpr uint16_t MAX_SPEED_DECI_KPH = 3000;
constexpr uint32_t SPEED_TIMEOUT_MS = 500;

enum class Inhibit : uint8_t {
    NONE,
    NO_SPEED,
    STALE_SPEED,
    INVALID_SPEED,
    NO_CONTROLLER,
    CAN_FAULT,
};

struct SpeedState {
    bool seen = false;
    bool invalid = false;
    uint16_t deciKph = 0;
    uint32_t receivedMs = 0;
};

inline bool decodeSpeed(bool extended, uint32_t id, const uint8_t *payload,
                        uint8_t length, uint16_t &deciKph) {
    if (!extended || id != SPEED_CAN_ID || length != 2 || payload == nullptr) {
        return false;
    }
    const uint16_t decoded = static_cast<uint16_t>(payload[0]) |
                             (static_cast<uint16_t>(payload[1]) << 8);
    if (decoded > MAX_SPEED_DECI_KPH) {
        return false;
    }
    deciKph = decoded;
    return true;
}

inline float interpolateMonotoneCubicV1(uint16_t deciKph, const uint16_t *speeds,
                                        const uint16_t *values, uint8_t count) {
    if (deciKph <= speeds[0]) return values[0] / 1000.0f;
    if (deciKph >= speeds[count - 1]) return values[count - 1] / 1000.0f;
    float tangents[8] = {};
    float secants[7] = {};
    for (uint8_t i = 0; i + 1 < count; ++i) {
        secants[i] = ((values[i + 1] - static_cast<float>(values[i])) / 1000.0f) /
                      (speeds[i + 1] - speeds[i]);
    }
    for (uint8_t i = 1; i + 1 < count; ++i) {
        const float leftSpan = speeds[i] - speeds[i - 1];
        const float rightSpan = speeds[i + 1] - speeds[i];
        const float weighted = (secants[i - 1] * rightSpan + secants[i] * leftSpan) /
                               (leftSpan + rightSpan);
        const float signSum = (secants[i - 1] < 0.0f ? -1.0f : 1.0f) +
                              (secants[i] < 0.0f ? -1.0f : 1.0f);
        float magnitude = __builtin_fabsf(secants[i - 1]);
        const float right = __builtin_fabsf(secants[i]);
        const float weightedHalf = 0.5f * __builtin_fabsf(weighted);
        if (right < magnitude) magnitude = right;
        if (weightedHalf < magnitude) magnitude = weightedHalf;
        tangents[i] = signSum * magnitude;
    }
    tangents[0] = (3.0f * secants[0] - tangents[1]) / 2.0f;
    tangents[count - 1] = (3.0f * secants[count - 2] - tangents[count - 2]) / 2.0f;
    for (uint8_t i = 0; i + 1 < count; ++i) {
        if (deciKph >= speeds[i + 1]) continue;
        const float span = speeds[i + 1] - speeds[i];
        const float t = (deciKph - speeds[i]) / span;
        const float t2 = t * t, t3 = t2 * t;
        const float y0 = values[i] / 1000.0f, y1 = values[i + 1] / 1000.0f;
        float result = (2 * t3 - 3 * t2 + 1) * y0 +
                       (t3 - 2 * t2 + t) * span * tangents[i] +
                       (-2 * t3 + 3 * t2) * y1 +
                       (t3 - t2) * span * tangents[i + 1];
        if (result < 0.0f) result = 0.0f;
        if (result > 1.0f) result = 1.0f;
        return result;
    }
    return values[count - 1] / 1000.0f;
}

inline float assistanceForSpeed(uint16_t deciKph) {
    // Same Steffen/D3 monotone-cubic-v1 algorithm, schema grid, and values as
    // the coordinator; AVR evaluates in binary32 before PWM quantization.
    static const uint16_t speeds[] = {0, 100, 200, 300, 600, 1000, 1600, 2500};
    static const uint16_t assistance[] = {1000, 889, 778, 667, 381, 0, 0, 0};
    return interpolateMonotoneCubicV1(deciKph, speeds, assistance,
                                      sizeof(speeds) / sizeof(speeds[0]));
}

inline Inhibit inhibitReason(const SpeedState &speed, uint32_t now,
                             bool controllerFresh, bool canHealthy) {
    if (!canHealthy) return Inhibit::CAN_FAULT;
    if (!controllerFresh) return Inhibit::NO_CONTROLLER;
    if (speed.invalid) return Inhibit::INVALID_SPEED;
    if (!speed.seen) return Inhibit::NO_SPEED;
    if (now - speed.receivedMs > SPEED_TIMEOUT_MS) return Inhibit::STALE_SPEED;
    return Inhibit::NONE;
}

inline uint8_t boundedDuty(float assistance, uint8_t ceiling) {
    if (assistance < 0.0f) assistance = 0.0f;
    if (assistance > 1.0f) assistance = 1.0f;
    // Explicit policy: truncate to the greatest representable duty not above target.
    return static_cast<uint8_t>(assistance * ceiling);
}

}  // namespace servotronic
