#pragma once

#include <stdint.h>

#include "can_ids.h"

namespace button_pad {

constexpr uint8_t STATUS_OK = 0;
constexpr uint8_t STATUS_LOCAL_FAULT = 1;
constexpr uint8_t STATUS_CAN_SEND_FAILED = 2;

enum class DeviceState : uint8_t {
    BOOTING,
    DISCOVERING,
    OPERATIONAL,
    CONTROLLER_LOST,
    INCOMPATIBLE,
    LOCAL_FAULT,
};

struct SequenceState {
    uint8_t hello = 0;
    uint8_t heartbeat = 0;
    uint8_t lastSent = 0;

    uint8_t nextHello() {
        const uint8_t sequence = hello;
        hello = static_cast<uint8_t>(hello + 1);
        lastSent = sequence;
        return sequence;
    }

    uint8_t nextHeartbeat() {
        const uint8_t sequence = heartbeat;
        heartbeat = static_cast<uint8_t>(heartbeat + 1);
        lastSent = sequence;
        return sequence;
    }
};

inline void putUint16(uint8_t *payload, uint16_t value, uint8_t lowByte, uint8_t highByte) {
    payload[lowByte] = static_cast<uint8_t>(value & 0xFF);
    payload[highByte] = static_cast<uint8_t>(value >> 8);
}

inline void encodeHello(
    uint8_t *payload,
    uint8_t protocolVersion,
    uint16_t deviceId,
    uint16_t deviceSession,
    uint8_t sequence
) {
    payload[BUTTON_PAD_HELLO_PROTOCOL_VERSION_BYTE] = protocolVersion;
    putUint16(payload, deviceId, BUTTON_PAD_HELLO_DEVICE_ID_LOW_BYTE,
              BUTTON_PAD_HELLO_DEVICE_ID_HIGH_BYTE);
    putUint16(payload, deviceSession, BUTTON_PAD_HELLO_DEVICE_SESSION_ID_LOW_BYTE,
              BUTTON_PAD_HELLO_DEVICE_SESSION_ID_HIGH_BYTE);
    payload[BUTTON_PAD_HELLO_SEQUENCE_BYTE] = sequence;
}

inline void encodeHeartbeat(
    uint8_t *payload,
    uint16_t deviceId,
    uint16_t deviceSession,
    uint16_t controllerSession,
    uint8_t sequence,
    uint8_t status
) {
    putUint16(payload, deviceId, BUTTON_PAD_HEARTBEAT_DEVICE_ID_LOW_BYTE,
              BUTTON_PAD_HEARTBEAT_DEVICE_ID_HIGH_BYTE);
    putUint16(payload, deviceSession, BUTTON_PAD_HEARTBEAT_DEVICE_SESSION_ID_LOW_BYTE,
              BUTTON_PAD_HEARTBEAT_DEVICE_SESSION_ID_HIGH_BYTE);
    putUint16(payload, controllerSession, BUTTON_PAD_HEARTBEAT_CONTROLLER_SESSION_ID_LOW_BYTE,
              BUTTON_PAD_HEARTBEAT_CONTROLLER_SESSION_ID_HIGH_BYTE);
    payload[BUTTON_PAD_HEARTBEAT_SEQUENCE_BYTE] = sequence;
    payload[BUTTON_PAD_HEARTBEAT_STATUS_BYTE] = status;
}

struct DeviceStatus {
    DeviceState state;
    uint8_t code;
};

inline DeviceStatus heartbeatSendCompleted(DeviceStatus current, bool succeeded) {
    if (!succeeded && current.state == DeviceState::OPERATIONAL) {
        return {DeviceState::LOCAL_FAULT, STATUS_CAN_SEND_FAILED};
    }
    if (succeeded && current.state == DeviceState::LOCAL_FAULT &&
        current.code == STATUS_CAN_SEND_FAILED) {
        return {DeviceState::OPERATIONAL, STATUS_OK};
    }
    return current;
}

inline bool shouldBeginDiscovery(
    DeviceState state,
    bool controllerLease,
    bool leaseFresh
) {
    return controllerLease && !leaseFresh &&
           (state == DeviceState::OPERATIONAL || state == DeviceState::LOCAL_FAULT);
}

}  // namespace button_pad
