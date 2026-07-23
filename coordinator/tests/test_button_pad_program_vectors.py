from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from e87canbus.domain.button_pad import ButtonPadProgram, pack_button_pad_transfers
from e87canbus.protocol.can import (
    BUTTON_PAD_TRANSFER_MAX_LENGTH,
    decode_button_pad_commands,
    decode_button_pad_program,
    encode_button_pad_program,
)

VECTOR_PATH = Path(__file__).parents[2] / "protocol/test-vectors/button-pad-program-v2.json"


def vectors() -> dict[str, Any]:
    return json.loads(VECTOR_PATH.read_text())


@pytest.mark.parametrize("vector", vectors()["programs"], ids=lambda item: item["name"])
def test_valid_program_vectors_round_trip_exact_wire_bytes(vector: dict[str, Any]) -> None:
    payloads = tuple(bytes.fromhex(value) for value in vector["commands_hex"])
    canonical = ButtonPadProgram(payloads)

    assert decode_button_pad_program(canonical.payloads[0]).replace_all
    assert all(
        encode_button_pad_program(decode_button_pad_program(value)) == value for value in payloads
    )


@pytest.mark.parametrize("vector", vectors()["programs"], ids=lambda item: item["name"])
def test_packing_transfers_is_bounded_and_losslessly_recovers_records(
    vector: dict[str, Any],
) -> None:
    records = tuple(bytes.fromhex(value) for value in vector["commands_hex"])
    transfers = pack_button_pad_transfers(ButtonPadProgram(records))

    assert all(0 < len(transfer) <= BUTTON_PAD_TRANSFER_MAX_LENGTH for transfer in transfers)
    assert len(transfers) == -(-len(records) // (BUTTON_PAD_TRANSFER_MAX_LENGTH // 16))
    recovered = tuple(
        encode_button_pad_program(command)
        for transfer in transfers
        for command in decode_button_pad_commands(transfer)
    )
    assert recovered == records


def test_decode_button_pad_commands_rejects_unaligned_or_oversized_transfers() -> None:
    valid_record = bytes.fromhex("02810100010000ff00000000000000ff")
    with pytest.raises(ValueError):
        decode_button_pad_commands(valid_record[:-1])
    with pytest.raises(ValueError):
        decode_button_pad_commands(valid_record * 5)
    with pytest.raises(ValueError):
        decode_button_pad_commands(b"")


@pytest.mark.parametrize("vector", vectors()["invalid_commands"], ids=lambda item: item["name"])
def test_invalid_program_vectors_are_rejected(vector: dict[str, Any]) -> None:
    payload = bytes.fromhex(vector["payload_hex"])
    with pytest.raises(ValueError):
        decode_button_pad_program(payload)
    with pytest.raises(ValueError):
        ButtonPadProgram((payload,))
