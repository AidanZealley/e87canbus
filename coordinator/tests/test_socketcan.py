import can
import pytest
from e87canbus.adapters.socketcan import (
    SocketCanBus,
    from_python_can_message,
    to_python_can_message,
)
from e87canbus.protocol.can import CanFrame


class FakePythonCanBus:
    def shutdown(self) -> None:
        pass


def test_socketcan_opens_configured_channel_with_socketcan_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened_with: dict[str, str] = {}

    def open_bus(*, interface: str, channel: str) -> FakePythonCanBus:
        opened_with.update(interface=interface, channel=channel)
        return FakePythonCanBus()

    monkeypatch.setattr(can, "Bus", open_bus)

    bus = SocketCanBus("can2")
    bus.shutdown()

    assert opened_with == {"interface": "socketcan", "channel": "can2"}


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
