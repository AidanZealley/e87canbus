"""Console-host SSE event models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConsoleLiveModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConsoleCanState(ConsoleLiveModel):
    interface: Literal["kcan"] = "kcan"
    connected: bool
    frames_received: int = Field(ge=0)
    fault: str | None


class ConsoleSnapshotData(ConsoleLiveModel):
    can: ConsoleCanState


class ConsoleSnapshotEvent(ConsoleLiveModel):
    """Complete local state sent by the console host's SSE endpoint."""

    type: Literal["console.snapshot"]
    data: ConsoleSnapshotData
