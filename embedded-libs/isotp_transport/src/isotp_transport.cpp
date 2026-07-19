#include "isotp_transport.h"

#include <stdarg.h>

namespace {

e87canbus::IsoTpSendFrame activeSendFrame = nullptr;

class SendFrameScope {
   public:
    explicit SendFrameScope(e87canbus::IsoTpSendFrame sendFrame)
        : previousSendFrame_(activeSendFrame) {
        activeSendFrame = sendFrame;
    }

    ~SendFrameScope() { activeSendFrame = previousSendFrame_; }

    SendFrameScope(const SendFrameScope &) = delete;
    SendFrameScope &operator=(const SendFrameScope &) = delete;

   private:
    e87canbus::IsoTpSendFrame previousSendFrame_;
};

}  // namespace

extern "C" int isotp_user_send_can(uint32_t arbitrationId, const uint8_t *data, uint8_t size) {
    return activeSendFrame != nullptr && activeSendFrame(arbitrationId, data, size)
               ? ISOTP_RET_OK
               : ISOTP_RET_NOSPACE;
}

extern "C" uint32_t isotp_user_get_us(void) { return micros(); }

extern "C" void isotp_user_debug(const char *message, ...) {
    (void)message;
}

namespace e87canbus {

IsoTpTransport::IsoTpTransport(uint32_t transmitId, IsoTpSendFrame sendFrame)
    : sendFrame_(sendFrame) {
    isotp_init_link(&link_, transmitId, sendBuffer_, sizeof(sendBuffer_), receiveBuffer_,
                    sizeof(receiveBuffer_));
}

void IsoTpTransport::onFrame(const uint8_t *data, uint8_t length) {
    SendFrameScope scope(sendFrame_);
    isotp_on_can_message(&link_, data, length);
}

void IsoTpTransport::poll() {
    SendFrameScope scope(sendFrame_);
    isotp_poll(&link_);
}

bool IsoTpTransport::send(const uint8_t *payload, uint16_t length) {
    SendFrameScope scope(sendFrame_);
    return length <= ISOTP_MAXIMUM_PAYLOAD_LENGTH &&
           isotp_send(&link_, payload, length) == ISOTP_RET_OK;
}

bool IsoTpTransport::receive(uint8_t *payload, uint16_t capacity, uint16_t *length) {
    SendFrameScope scope(sendFrame_);
    uint32_t received = 0;
    if (capacity > ISOTP_MAXIMUM_PAYLOAD_LENGTH ||
        isotp_receive(&link_, payload, capacity, &received) != ISOTP_RET_OK) {
        return false;
    }
    *length = static_cast<uint16_t>(received);
    return true;
}

}  // namespace e87canbus
