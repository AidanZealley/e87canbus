"""Placeholder DSC command objects."""

from __future__ import annotations

from dataclasses import dataclass

from e87canbus.events import DscCommand


@dataclass(frozen=True)
class DscOffRequest:
    command: DscCommand = DscCommand.OFF_REQUEST
    verified_replay_payload: bytes | None = None

    def to_replay_frames(self) -> tuple[bytes, ...]:
        raise NotImplementedError(
            "DSC replay requires verified candump captures and counter analysis",
        )
