"""Shared error response models exposed by every HTTP API surface."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

ApiProblemCode = Literal[
    "validation_error",
    "settings_revision_conflict",
    "settings_storage_error",
    "profile_not_found",
    "profile_revision_conflict",
    "profile_name_conflict",
    "profile_storage_error",
    "runtime_queue_full",
    "controller_unavailable",
    "command_timeout",
    "simulation_device_unavailable",
    "controller_failed",
    "feature_unavailable",
    "controller_runtime_error",
]


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: list[str | int]
    message: str
    type: str


class ApiProblemDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ApiProblemCode
    message: str
    current_revision: int | None = None
    issues: list[ValidationIssue] | None = None


class ApiProblemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ApiProblemDetail
