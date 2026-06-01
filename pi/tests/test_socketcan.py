from e87canbus.can_io import CanFrame
from e87canbus.socketcan import from_python_can_message, to_python_can_message

import can


def test_socketcan_frame_conversion_round_trip() -> None:
    frame = CanFrame(arbitration_id=0x700, data=b"\x00\x01", is_extended_id=False)

    message = to_python_can_message(frame)

    assert message.arbitration_id == 0x700
    assert bytes(message.data) == b"\x00\x01"
    assert not message.is_extended_id
    assert from_python_can_message(message) == frame


def test_socketcan_extended_frame_conversion() -> None:
    message = can.Message(arbitration_id=0x18DAF110, data=[1, 2, 3], is_extended_id=True)

    frame = from_python_can_message(message)

    assert frame == CanFrame(0x18DAF110, b"\x01\x02\x03", is_extended_id=True)
