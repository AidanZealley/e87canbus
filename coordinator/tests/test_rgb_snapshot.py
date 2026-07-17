import pytest
from e87canbus.application.events import BUTTON_LED_COUNT
from e87canbus.protocol.can import (
    RGB_SNAPSHOT_LENGTH,
    RgbSnapshotPayload,
    decode_rgb_snapshot,
    encode_rgb_snapshot,
)


def test_rgb_snapshot_round_trips_logical_button_order() -> None:
    snapshot = RgbSnapshotPayload(
        tuple((index, index + 1, index + 2) for index in range(BUTTON_LED_COUNT))
    )

    payload = encode_rgb_snapshot(snapshot)

    assert len(payload) == RGB_SNAPSHOT_LENGTH == 48
    assert payload[:6] == b"\x00\x01\x02\x01\x02\x03"
    assert decode_rgb_snapshot(payload) == snapshot


def test_rgb_snapshot_rejects_non_exact_payload_length() -> None:
    with pytest.raises(ValueError, match="exactly 48"):
        decode_rgb_snapshot(bytes(RGB_SNAPSHOT_LENGTH - 1))
