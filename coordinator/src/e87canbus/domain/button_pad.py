"""Canonical resolved-track programs requested from the button-pad display."""

from dataclasses import dataclass
from typing import Final

from e87canbus.protocol.can import (
    BUTTON_PAD_COMMAND_LENGTH,
    BUTTON_PAD_TRACK_BLINK,
    BUTTON_PAD_TRACK_BREATHE,
    BUTTON_PAD_TRACK_SOLID,
    BUTTON_PAD_TRANSFER_MAX_LENGTH,
    ButtonPadTrackCommandPayload,
    ButtonPadTrackPayload,
    decode_button_pad_program,
    encode_button_pad_program,
)

BUTTON_PAD_PROGRAM_ENCODING: Final = "e87-button-pad-v2"
Rgb = tuple[int, int, int]


@dataclass(frozen=True)
class ButtonPadProgram:
    payloads: tuple[bytes, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.payloads) <= 16:
            raise ValueError("button-pad program must contain between one and 16 commands")
        commands = tuple(decode_button_pad_program(payload) for payload in self.payloads)
        if not commands[0].replace_all or any(command.replace_all for command in commands[1:]):
            raise ValueError("button-pad program must begin with exactly one replace-all command")
        if not commands[-1].commit or any(command.commit for command in commands[:-1]):
            raise ValueError("button-pad program must commit exactly once on its final command")
        covered = 0
        for command_value in commands:
            if covered & command_value.target_mask:
                raise ValueError("button-pad program must assign every button exactly once")
            covered |= command_value.target_mask
        if covered != 0xFFFF:
            raise ValueError("button-pad program must assign every button exactly once")


def solid_track(rgb: Rgb) -> ButtonPadTrackPayload:
    return ButtonPadTrackPayload(BUTTON_PAD_TRACK_SOLID, rgb, final_rgb=rgb)


def blink_track(
    rgb: Rgb, on_ms: int, off_ms: int, repeat: int, final_rgb: Rgb
) -> ButtonPadTrackPayload:
    return ButtonPadTrackPayload(BUTTON_PAD_TRACK_BLINK, rgb, on_ms, off_ms, repeat, final_rgb)


def breathe_track(
    rgb: Rgb,
    minimum: int,
    maximum: int,
    period_ms: int,
    repeat: int = 0,
    final_rgb: Rgb = (0, 0, 0),
) -> ButtonPadTrackPayload:
    return ButtonPadTrackPayload(
        BUTTON_PAD_TRACK_BREATHE, rgb, period_ms, minimum | (maximum << 8), repeat, final_rgb
    )


def pack_button_pad_transfers(program: ButtonPadProgram) -> tuple[bytes, ...]:
    """Concatenate the resolved command records into 64-byte ISO-TP transfers.

    Packing is a transport concern only: ``program.payloads`` stays one record per
    entry for the live-events contract, while the device receives up to four records
    per transfer so the common case is a single transfer with no inter-command pacing.
    """

    per_transfer = BUTTON_PAD_TRANSFER_MAX_LENGTH // BUTTON_PAD_COMMAND_LENGTH
    records = program.payloads
    return tuple(
        b"".join(records[offset : offset + per_transfer])
        for offset in range(0, len(records), per_transfer)
    )


def resolve_button_pad_tracks(program: ButtonPadProgram) -> tuple[ButtonPadTrackPayload, ...]:
    tracks: list[ButtonPadTrackPayload] | None = None
    for payload in program.payloads:
        decoded = decode_button_pad_program(payload)
        if decoded.replace_all:
            tracks = [decoded.track] * 16
        if tracks is None:
            raise ValueError("button-pad program must begin with a replace-all command")
        for index in range(16):
            if decoded.target_mask & (1 << index):
                tracks[index] = decoded.track
    assert tracks is not None
    return tuple(tracks)


def resolved_button_pad_program(tracks: tuple[ButtonPadTrackPayload, ...]) -> ButtonPadProgram:
    if len(tracks) != 16:
        raise ValueError("resolved button-pad programs require exactly 16 tracks")
    grouped: dict[ButtonPadTrackPayload, int] = {}
    for index, track in enumerate(tracks):
        grouped[track] = grouped.get(track, 0) | (1 << index)
    commands = [(mask, track, index == 0) for index, (track, mask) in enumerate(grouped.items())]
    payloads = [
        encode_button_pad_program(
            ButtonPadTrackCommandPayload(replace_all, mask, track, index == len(commands) - 1)
        )
        for index, (mask, track, replace_all) in enumerate(commands)
    ]
    return ButtonPadProgram(tuple(payloads))


def static_button_pad_program(rgb: tuple[Rgb, ...]) -> ButtonPadProgram:
    return resolved_button_pad_program(tuple(solid_track(value) for value in rgb))
