#pragma once
#include <stdint.h>

namespace servotronic {
constexpr uint8_t PROTOCOL_VERSION = 1;
constexpr uint32_t HELLO_ID = 0x705;
constexpr uint32_t WELCOME_ID = 0x706;
constexpr uint32_t HEARTBEAT_ID = 0x707;
enum class AckKind : uint8_t { NONE, HELLO, HEARTBEAT };
struct AckTracker {
    AckKind kind = AckKind::NONE;
    uint8_t sequence = 0;
    uint16_t controllerSession = 0;
    void expect(AckKind nextKind, uint8_t nextSequence) {
        kind = nextKind; sequence = nextSequence;
    }
    bool accept(uint8_t echoedSequence, uint16_t acknowledgedControllerSession) {
        if (kind == AckKind::NONE || echoedSequence != sequence) return false;
        if (kind == AckKind::HEARTBEAT && controllerSession != acknowledgedControllerSession)
            return false;
        controllerSession = acknowledgedControllerSession;
        kind = AckKind::NONE;
        return true;
    }
};
inline uint16_t u16(const uint8_t *p, uint8_t offset) {
    return static_cast<uint16_t>(p[offset]) | (static_cast<uint16_t>(p[offset + 1]) << 8);
}
inline void put16(uint8_t *p, uint8_t offset, uint16_t value) {
    p[offset] = static_cast<uint8_t>(value); p[offset + 1] = static_cast<uint8_t>(value >> 8);
}
inline void encodeHello(uint8_t *p, uint16_t id, uint16_t session, uint8_t sequence) {
    p[0] = PROTOCOL_VERSION; put16(p, 1, id); put16(p, 3, session); p[5] = sequence;
    p[6] = 0; p[7] = 0;
}
inline void encodeHeartbeat(uint8_t *p, uint16_t id, uint16_t session,
                            uint16_t controller, uint8_t sequence, uint8_t status) {
    put16(p, 0, id); put16(p, 2, session); put16(p, 4, controller);
    p[6] = sequence; p[7] = status;
}
}  // namespace servotronic
