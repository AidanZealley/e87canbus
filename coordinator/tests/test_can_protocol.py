import pytest
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.can import (
    ArduinoButtonEventPayload,
    CanFrame,
    LedSnapshotPayload,
    RoutedCanFrame,
    decode_button_event,
    decode_led_snapshot,
    encode_button_event,
    encode_led_snapshot,
)


def test_routed_envelope_preserves_network_without_mutating_frame() -> None:
    frame = CanFrame(0x123, b"\x01\x02")

    routed = RoutedCanFrame(CanNetwork.PTCAN, frame)

    assert routed.network is CanNetwork.PTCAN
    assert routed.frame is frame
    assert not hasattr(frame, "network")


def test_encode_and_decode_arduino_button_event() -> None:
    ids = CustomCanIds()
    frame = encode_button_event(ArduinoButtonEventPayload(button_index=4, pressed=True), ids)

    assert frame.arbitration_id == 0x700
    assert frame.data == bytes([4, 1])
    assert decode_button_event(frame, ids) == ArduinoButtonEventPayload(
        button_index=4,
        pressed=True,
    )


@pytest.mark.parametrize(
    ("colour_codes", "expected_data"),
    [
        ((0,) * 16, b"\x00\x00\x00\x00\x00\x00\x00\x00"),
        ((3, 0, 0, 5) + (0,) * 12, b"\x03\x50\x00\x00\x00\x00\x00\x00"),
        ((3, 4, 2, 1, 5, 0) + (0,) * 10, b"\x43\x12\x05\x00\x00\x00\x00\x00"),
    ],
)
def test_encode_and_decode_led_snapshot_golden_vectors(
    colour_codes: tuple[int, ...], expected_data: bytes
) -> None:
    ids = CustomCanIds()
    payload = LedSnapshotPayload(colour_codes)
    frame = encode_led_snapshot(payload, ids)

    assert frame.arbitration_id == 0x701
    assert frame.data == expected_data
    assert decode_led_snapshot(frame, ids) == payload


def test_reject_invalid_payload_lengths() -> None:
    ids = CustomCanIds()

    with pytest.raises(ValueError, match="button event payload"):
        decode_button_event(CanFrame(ids.button_event, b"\x01"), ids)

    with pytest.raises(ValueError, match="LED snapshot payload"):
        decode_led_snapshot(CanFrame(ids.led_snapshot, b"\x00" * 7), ids)


def test_led_snapshot_rejects_invalid_final_nibble_without_payload() -> None:
    ids = CustomCanIds()
    frame = CanFrame(ids.led_snapshot, b"\x00" * 7 + b"\x60")

    with pytest.raises(ValueError, match="invalid colour"):
        decode_led_snapshot(frame, ids)


def test_led_snapshot_payload_rejects_partial_state() -> None:
    with pytest.raises(ValueError, match="exactly 16"):
        LedSnapshotPayload((0,) * 15)
