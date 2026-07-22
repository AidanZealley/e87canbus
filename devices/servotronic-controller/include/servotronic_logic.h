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
    CAN_FAULT,
};

constexpr uint8_t CURVE_POINT_COUNT = 8;
constexpr uint8_t CURVE_PROTOCOL_VERSION = 1;
constexpr uint8_t CURVE_SET_OPCODE = 1;
constexpr uint8_t CURVE_STATUS_OPCODE = 2;
constexpr uint8_t CURVE_SCHEMA_VERSION = 1;
constexpr uint8_t CURVE_INTERPOLATION_VERSION = 1;
constexpr uint8_t CURVE_PAYLOAD_LENGTH = 44;
constexpr uint8_t CURVE_STATUS_LENGTH = 19;

enum class CurveResult : uint8_t {
    ACCEPTED = 0, BAD_LENGTH = 1, UNSUPPORTED = 2, BAD_GRID = 3,
    BAD_VALUES = 4, BAD_CRC = 5,
};
enum class CurveSource : uint8_t { BUILTIN_FALLBACK = 0, COORDINATOR_RAM = 1 };

struct ActiveCurve {
    uint16_t speeds[CURVE_POINT_COUNT] = {0, 100, 200, 300, 600, 1000, 1600, 2500};
    uint16_t assistance[CURVE_POINT_COUNT] = {1000, 889, 778, 667, 381, 0, 0, 0};
    uint32_t revision = 0;
    uint32_t crc32 = 0;
    CurveSource source = CurveSource::BUILTIN_FALLBACK;
};

inline uint16_t readU16(const uint8_t *p) {
    return static_cast<uint16_t>(p[0]) | (static_cast<uint16_t>(p[1]) << 8);
}
inline uint32_t readU32(const uint8_t *p) {
    return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
           (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
}
inline void writeU16(uint8_t *p, uint16_t value) {
    p[0] = value & 0xff; p[1] = value >> 8;
}
inline void writeU32(uint8_t *p, uint32_t value) {
    p[0] = value & 0xff; p[1] = (value >> 8) & 0xff;
    p[2] = (value >> 16) & 0xff; p[3] = value >> 24;
}
inline uint32_t crc32(const uint8_t *payload, uint8_t length) {
    uint32_t crc = 0xffffffffUL;
    for (uint8_t i = 0; i < length; ++i) {
        crc ^= payload[i];
        for (uint8_t bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xedb88320UL & (0UL - (crc & 1UL)));
    }
    return crc ^ 0xffffffffUL;
}

inline CurveResult applyCurvePayload(const uint8_t *payload, uint16_t length,
                                     ActiveCurve &active) {
    if (payload == nullptr || length != CURVE_PAYLOAD_LENGTH) return CurveResult::BAD_LENGTH;
    if (payload[0] != CURVE_PROTOCOL_VERSION || payload[1] != CURVE_SET_OPCODE ||
        payload[2] != CURVE_SCHEMA_VERSION || payload[3] != CURVE_INTERPOLATION_VERSION)
        return CurveResult::UNSUPPORTED;
    if (crc32(payload, 40) != readU32(payload + 40)) return CurveResult::BAD_CRC;
    static const uint16_t grid[CURVE_POINT_COUNT] = {0, 100, 200, 300, 600, 1000, 1600, 2500};
    ActiveCurve staged;
    for (uint8_t i = 0; i < CURVE_POINT_COUNT; ++i) {
        staged.speeds[i] = readU16(payload + 8 + i * 2);
        staged.assistance[i] = readU16(payload + 24 + i * 2);
        if (staged.speeds[i] != grid[i]) return CurveResult::BAD_GRID;
        if (staged.assistance[i] > 1000 ||
            (i != 0 && staged.assistance[i - 1] < staged.assistance[i]))
            return CurveResult::BAD_VALUES;
    }
    staged.revision = readU32(payload + 4);
    staged.crc32 = readU32(payload + 40);
    staged.source = CurveSource::COORDINATOR_RAM;
    active = staged;  // Single control-loop-boundary activation; no partial curve is observable.
    return CurveResult::ACCEPTED;
}

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

inline float assistanceForSpeed(uint16_t deciKph, const ActiveCurve &curve) {
    // Same Steffen/D3 monotone-cubic-v1 algorithm, schema grid, and values as
    // the coordinator; AVR evaluates in binary32 before PWM quantization.
    return interpolateMonotoneCubicV1(deciKph, curve.speeds, curve.assistance,
                                      CURVE_POINT_COUNT);
}

inline float assistanceForSpeed(uint16_t deciKph) {
    const ActiveCurve fallback;
    return assistanceForSpeed(deciKph, fallback);
}

inline Inhibit inhibitReason(const SpeedState &speed, uint32_t now, bool canHealthy) {
    if (!canHealthy) return Inhibit::CAN_FAULT;
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
