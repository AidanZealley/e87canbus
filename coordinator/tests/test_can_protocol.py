import pytest
from e87canbus.config import CustomCanIds
from e87canbus.protocol.can import (
    ArduinoButtonEventPayload,
    CanFrame,
    LedUpdatePayload,
    decode_button_event,
    decode_led_update,
    encode_button_event,
    encode_led_update,
)


def test_encode_and_decode_arduino_button_event() -> None:
    ids = CustomCanIds()
    frame = encode_button_event(ArduinoButtonEventPayload(button_index=4, pressed=True), ids)

    assert frame.arbitration_id == 0x700
    assert frame.data == bytes([4, 1])
    assert decode_button_event(frame, ids) == ArduinoButtonEventPayload(
        button_index=4,
        pressed=True,
    )


def test_decode_pi_led_update_payload() -> None:
    ids = CustomCanIds()
    frame = encode_led_update(LedUpdatePayload(button_index=2, colour_code=3), ids)

    assert frame.arbitration_id == 0x701
    assert decode_led_update(frame, ids) == LedUpdatePayload(button_index=2, colour_code=3)


def test_reject_invalid_payload_lengths() -> None:
    ids = CustomCanIds()

    with pytest.raises(ValueError, match="button event payload"):
        decode_button_event(CanFrame(ids.button_event, b"\x01"), ids)

    with pytest.raises(ValueError, match="LED update payload"):
        decode_led_update(CanFrame(ids.led_update, b"\x01"), ids)
