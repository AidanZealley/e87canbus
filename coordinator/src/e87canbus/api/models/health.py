"""Health endpoint response models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LivenessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["live"] = "live"


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ready", "not_ready"]
    boot_id: str = Field(min_length=1)
