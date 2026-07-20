"""Steering-profile HTTP request and response models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from e87canbus.features.steering import (
    STEERING_CURVE_V1_SPEEDS_DECI_KPH,
    STEERING_PROFILE_NAME_MAX_LENGTH,
)

STEERING_CURVE_POINT_COUNT = len(STEERING_CURVE_V1_SPEEDS_DECI_KPH)
CANONICAL_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SteeringCurvePointRequest(StrictRequest):
    speed_deci_kph: int = Field(ge=0)
    assistance_per_mille: int = Field(ge=0, le=1000)


class SteeringCurveDefinitionRequest(StrictRequest):
    schema_version: Literal[1]
    points: list[SteeringCurvePointRequest] = Field(
        min_length=STEERING_CURVE_POINT_COUNT,
        max_length=STEERING_CURVE_POINT_COUNT,
    )


class CreateProfileRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=STEERING_PROFILE_NAME_MAX_LENGTH)
    definition: SteeringCurveDefinitionRequest


class UpdateProfileRequest(CreateProfileRequest):
    expected_revision: int = Field(ge=1)


class SteeringCurvePointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    speed_deci_kph: int = Field(ge=0)
    assistance_per_mille: int = Field(ge=0, le=1000)


class SteeringCurveDefinitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    schema_version: Literal[1]
    points: tuple[SteeringCurvePointResponse, ...] = Field(
        min_length=STEERING_CURVE_POINT_COUNT,
        max_length=STEERING_CURVE_POINT_COUNT,
    )


class SteeringProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    profile_id: str = Field(pattern=CANONICAL_UUID_PATTERN)
    name: str = Field(min_length=1, max_length=STEERING_PROFILE_NAME_MAX_LENGTH)
    revision: int = Field(ge=1)
    definition: SteeringCurveDefinitionResponse
    created_at: str
    updated_at: str
