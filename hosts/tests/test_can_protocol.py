import pytest
from e87canbus.protocol.can import (
    CanFrame,
    DeviceHeartbeatPayload,
    DeviceHelloPayload,
    DeviceWelcomeAckPayload,
    decode_heartbeat,
    decode_hello,
    decode_welcome_ack,
    encode_heartbeat,
    encode_hello,
    encode_welcome_ack,
)


@pytest.mark.parametrize(
    ("hello_id", "ack_id", "heartbeat_id"),
    [
        (0x705, 0x706, 0x707),
    ],
)
def test_registry_conformance_vectors_for_servotronic(
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

    assert decode_hello(encode_hello(hello, 0x705), 0x705) == hello
    assert decode_welcome_ack(encode_welcome_ack(ack, 0x706), 0x706) == ack
    assert decode_heartbeat(encode_heartbeat(heartbeat, 0x707), 0x707) == heartbeat


@pytest.mark.parametrize(
    "payload",
    [
        b"\x01\x01\x00\x34\x12\x56\x00",
        b"\x01\x01\x00\x34\x12\x56\x00\x01",
    ],
)
def test_registry_hello_rejects_wrong_dlc_and_reserved_bytes(payload: bytes) -> None:
    with pytest.raises(ValueError, match="reserved|exactly 8"):
        decode_hello(CanFrame(0x705, payload), 0x705)


def test_registry_ack_rejects_reserved_response_code() -> None:
    frame = CanFrame(0x706, bytes.fromhex("12 01 00 34 12 CD AB 56"))

    with pytest.raises(ValueError, match="response code"):
        decode_welcome_ack(frame, 0x706)


def test_registry_codecs_reject_invalid_fields_and_frame_boundaries() -> None:
    with pytest.raises(ValueError, match="16-bit"):
        DeviceHelloPayload(1, 0x10000, 1, 0)
    with pytest.raises(ValueError, match="response_code"):
        DeviceWelcomeAckPayload(1, 2, 1, 1, 1, 0)
    with pytest.raises(ValueError, match="standard"):
        encode_hello(DeviceHelloPayload(1, 1, 1, 0), 0x800)
    with pytest.raises(ValueError, match="standard"):
        decode_hello(CanFrame(0x705, b"\x00" * 8, is_extended_id=True), 0x705)
    assert decode_hello(CanFrame(0x123, b"\x00" * 8), 0x705) is None
