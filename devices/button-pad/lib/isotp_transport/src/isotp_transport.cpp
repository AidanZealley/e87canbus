#include "isotp_transport.h"

#include <stdarg.h>


namespace {
button_pad::IsoTpSendFrame sendFrame = nullptr;
}

extern "C" int isotp_user_send_can(uint32_t arbitrationId, const uint8_t *data, uint8_t size) {
    return sendFrame != nullptr && sendFrame(arbitrationId, data, size) ? ISOTP_RET_OK
                                                                        : ISOTP_RET_NOSPACE;
}

extern "C" uint32_t isotp_user_get_us(void) { return micros(); }

extern "C" void isotp_user_debug(const char *message, ...) {
    (void)message;
}

namespace button_pad {

IsoTpTransport::IsoTpTransport(uint32_t transmitId, IsoTpSendFrame sender) {
    sendFrame = sender;
    isotp_init_link(&link_, transmitId, sendBuffer_,
                    sizeof(sendBuffer_), receiveBuffer_, sizeof(receiveBuffer_));
}

void IsoTpTransport::onFrame(const uint8_t *data, uint8_t length) {
    isotp_on_can_message(&link_, data, length);
}

void IsoTpTransport::poll() { isotp_poll(&link_); }

bool IsoTpTransport::send(const uint8_t *payload, uint16_t length) {
    return length <= ISOTP_MAXIMUM_PAYLOAD_LENGTH &&
           isotp_send(&link_, payload, length) == ISOTP_RET_OK;
}

bool IsoTpTransport::receive(uint8_t *payload, uint16_t capacity, uint16_t *length) {
    uint32_t received = 0;
    if (capacity > ISOTP_MAXIMUM_PAYLOAD_LENGTH ||
        isotp_receive(&link_, payload, capacity, &received) != ISOTP_RET_OK) {
        return false;
    }
    *length = static_cast<uint16_t>(received);
    return true;
}

}  // namespace button_pad
