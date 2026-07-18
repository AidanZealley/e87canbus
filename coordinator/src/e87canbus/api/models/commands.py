"""Strict command request and acknowledgement models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from e87canbus.api.models.steering import (
    CANONICAL_UUID_PATTERN,
    SteeringCurveDefinitionRequest,
)


class StrictCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SetMaximumAssistanceRequest(StrictCommandRequest):
    enabled: bool


class SetSteeringModeRequest(StrictCommandRequest):
    mode: Literal["auto", "manual"]
    manual_level: int | None = Field(default=None, ge=0)


class ActivateSteeringProfileRequest(StrictCommandRequest):
    profile_id: str = Field(pattern=CANONICAL_UUID_PATTERN)
    expected_revision: int = Field(ge=1)


class ActivateSteeringCurveRequest(StrictCommandRequest):
    definition: SteeringCurveDefinitionRequest


class CommandAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    accepted: Literal[True] = True
    boot_id: str
    revision: int = Field(ge=1)
