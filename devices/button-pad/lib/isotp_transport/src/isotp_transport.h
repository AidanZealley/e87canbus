#pragma once

#include <Arduino.h>

#include <isotp.h>

namespace button_pad {

constexpr uint16_t ISOTP_MAXIMUM_PAYLOAD_LENGTH = 64;

using IsoTpSendFrame = bool (*)(uint32_t arbitrationId, const uint8_t *data, uint8_t length);

class IsoTpTransport {
   public:
    IsoTpTransport(uint32_t transmitId, IsoTpSendFrame sendFrame);

    void onFrame(const uint8_t *data, uint8_t length);
    void poll();
    bool send(const uint8_t *payload, uint16_t length);
    bool receive(uint8_t *payload, uint16_t capacity, uint16_t *length);

   private:
    IsoTpLink link_{};
    uint8_t sendBuffer_[ISOTP_MAXIMUM_PAYLOAD_LENGTH] = {};
    uint8_t receiveBuffer_[ISOTP_MAXIMUM_PAYLOAD_LENGTH] = {};
};

}  // namespace button_pad
