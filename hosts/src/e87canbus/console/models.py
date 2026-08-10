"""Version 1 console live-state contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CONSOLE_PROTOCOL_VERSION: Literal[1] = 1
CONSOLE_SNAPSHOT_EVENT: Literal["console.snapshot"] = "console.snapshot"


class ConsoleLiveModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConsoleCanState(ConsoleLiveModel):
    interface: Literal["kcan"] = "kcan"
    connected: bool
    frames_received: int = Field(ge=0)
    fault: str | None


class ConsoleSnapshotData(ConsoleLiveModel):
    can: ConsoleCanState


class ConsoleSnapshot(ConsoleLiveModel):
    protocol_version: Literal[1] = CONSOLE_PROTOCOL_VERSION
    boot_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    emitted_at: datetime
    data: ConsoleSnapshotData
