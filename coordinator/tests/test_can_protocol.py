import pytest
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.can import (
    RGB_SNAPSHOT_LENGTH,
    ArduinoButtonEventPayload,
    CanFrame,
    DeviceHeartbeatPayload,
    DeviceHelloPayload,
    DeviceWelcomeAckPayload,
    RgbSnapshotPayload,
    RoutedCanFrame,
    decode_button_event,
    decode_heartbeat,
    decode_hello,
    decode_rgb_snapshot,
    decode_welcome_ack,
    encode_button_event,
    encode_heartbeat,
    encode_hello,
    encode_rgb_snapshot,
    encode_welcome_ack,
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
    ("rgb", "expected_data"),
    [
        (((0, 0, 0),) * 16, b"\x00" * 48),
        (((3, 0, 0), (5, 0, 0)) + ((0, 0, 0),) * 14, b"\x03\x00\x00\x05\x00\x00" + b"\x00" * 42),
    ],
)
def test_encode_and_decode_rgb_snapshot_golden_vectors(
    rgb: tuple[tuple[int, int, int], ...], expected_data: bytes
) -> None:
    payload = RgbSnapshotPayload(rgb)
    data = encode_rgb_snapshot(payload)

    assert data == expected_data
    assert decode_rgb_snapshot(data) == payload


def test_reject_invalid_payload_lengths() -> None:
    with pytest.raises(ValueError, match="button event payload"):
        decode_button_event(CanFrame(CustomCanIds().button_event, b"\x01"), CustomCanIds())

    with pytest.raises(ValueError, match="RGB snapshot payload"):
        decode_rgb_snapshot(b"\x00" * (RGB_SNAPSHOT_LENGTH - 1))


def test_rgb_snapshot_payload_rejects_partial_state() -> None:
    with pytest.raises(ValueError, match="exactly 16"):
        RgbSnapshotPayload(((0, 0, 0),) * 15)


@pytest.mark.parametrize(
    ("hello_id", "ack_id", "heartbeat_id"),
    [
        (0x702, 0x703, 0x704),
        (0x705, 0x706, 0x707),
    ],
)
def test_registry_conformance_vectors_for_both_role_id_families(
    hello_id: int,
    ack_id: int,
    heartbeat_id: int,
) -> None:
    hello = DeviceHelloPayload(1, 1, 0x1234, 0x56)
    ack = DeviceWelcomeAckPayload(1, 0, 1, 0x1234, 0xABCD, 0x56)
    heartbeat = DeviceHeartbeatPayload(1, 0x1234, 0xABCD, 0x57, 0)

    hello_frame = encode_hello(hello, hello_id)
    ack_frame = encode_welcome_ack(ack, ack_id)
    heartbeat_frame = encode_heartbeat(heartbeat, heartbeat_id)

    assert hello_frame.data == bytes.fromhex("01 01 00 34 12 56 00 00")
    assert ack_frame.data == bytes.fromhex("10 01 00 34 12 CD AB 56")
    assert heartbeat_frame.data == bytes.fromhex("01 00 34 12 CD AB 57 00")
    assert decode_hello(hello_frame, hello_id) == hello
    assert decode_welcome_ack(ack_frame, ack_id) == ack
    assert decode_heartbeat(heartbeat_frame, heartbeat_id) == heartbeat


def test_registry_codecs_round_trip_extreme_unsigned_values() -> None:
    hello = DeviceHelloPayload(0xFF, 0xFFFF, 0xFFFF, 0xFF)
    ack = DeviceWelcomeAckPayload(0xF, 1, 0xFFFF, 0xFFFF, 0xFFFF, 0xFF)
    heartbeat = DeviceHeartbeatPayload(0xFFFF, 0xFFFF, 0xFFFF, 0xFF, 0xFF)

    assert decode_hello(encode_hello(hello, 0x702), 0x702) == hello
    assert decode_welcome_ack(encode_welcome_ack(ack, 0x703), 0x703) == ack
    assert decode_heartbeat(encode_heartbeat(heartbeat, 0x704), 0x704) == heartbeat


@pytest.mark.parametrize(
    "payload",
    [
        b"\x01\x01\x00\x34\x12\x56\x00",
        b"\x01\x01\x00\x34\x12\x56\x00\x01",
    ],
)
def test_registry_hello_rejects_wrong_dlc_and_reserved_bytes(payload: bytes) -> None:
    with pytest.raises(ValueError, match="reserved|exactly 8"):
        decode_hello(CanFrame(0x702, payload), 0x702)


def test_registry_ack_rejects_reserved_response_code() -> None:
    frame = CanFrame(0x703, bytes.fromhex("12 01 00 34 12 CD AB 56"))

    with pytest.raises(ValueError, match="response code"):
        decode_welcome_ack(frame, 0x703)


def test_registry_codecs_reject_invalid_fields_and_frame_boundaries() -> None:
    with pytest.raises(ValueError, match="16-bit"):
        DeviceHelloPayload(1, 0x10000, 1, 0)
    with pytest.raises(ValueError, match="response_code"):
        DeviceWelcomeAckPayload(1, 2, 1, 1, 1, 0)
    with pytest.raises(ValueError, match="standard"):
        encode_hello(DeviceHelloPayload(1, 1, 1, 0), 0x800)
    with pytest.raises(ValueError, match="standard"):
        decode_hello(CanFrame(0x702, b"\x00" * 8, is_extended_id=True), 0x702)
    assert decode_hello(CanFrame(0x123, b"\x00" * 8), 0x702) is None


def test_button_and_led_codecs_reject_extended_frames_on_standard_ids() -> None:
    ids = CustomCanIds()

    with pytest.raises(ValueError, match="standard"):
        decode_button_event(CanFrame(ids.button_event, b"\x00\x01", True), ids)
