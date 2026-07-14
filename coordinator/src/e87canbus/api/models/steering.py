"""Request models for steering curves and stored profiles."""

from pydantic import BaseModel, ConfigDict, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SteeringCurvePointRequest(StrictRequest):
    speed_deci_kph: int
    assistance_per_mille: int


class SteeringCurveDefinitionRequest(StrictRequest):
    schema_version: int
    interpolation: str
    points: list[SteeringCurvePointRequest]


class CreateProfileRequest(StrictRequest):
    name: str
    definition: SteeringCurveDefinitionRequest


class UpdateProfileRequest(CreateProfileRequest):
    expected_revision: int = Field(ge=1)


class ActivateCurveRequest(StrictRequest):
    definition: SteeringCurveDefinitionRequest
    saved_profile_id: str | None = None
    saved_profile_revision: int | None = Field(default=None, ge=1)
