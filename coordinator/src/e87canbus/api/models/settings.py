"""Application-settings HTTP request and response models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from e87canbus.domain.application_settings import (
    MAX_RPM,
    MAX_TEMPERATURE_C,
    MIN_RPM,
    MIN_TEMPERATURE_C,
    SpeedUnit,
    TemperatureUnit,
)


class UpdateApplicationSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_revision: int = Field(ge=1)
    speed_unit: Literal["mph", "kmh"]
    temperature_unit: Literal["c", "f"]
    oil_warning_c: float = Field(ge=MIN_TEMPERATURE_C, le=MAX_TEMPERATURE_C)
    oil_critical_c: float = Field(ge=MIN_TEMPERATURE_C, le=MAX_TEMPERATURE_C)
    coolant_warning_c: float = Field(ge=MIN_TEMPERATURE_C, le=MAX_TEMPERATURE_C)
    coolant_critical_c: float = Field(ge=MIN_TEMPERATURE_C, le=MAX_TEMPERATURE_C)
    shift_stage_1_rpm: int = Field(ge=MIN_RPM, le=MAX_RPM)
    shift_stage_2_rpm: int = Field(ge=MIN_RPM, le=MAX_RPM)
    redline_rpm: int = Field(ge=MIN_RPM, le=MAX_RPM)


class ApplicationSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    revision: int = Field(ge=1)
    speed_unit: SpeedUnit
    temperature_unit: TemperatureUnit
    oil_warning_c: float
    oil_critical_c: float
    coolant_warning_c: float
    coolant_critical_c: float
    shift_stage_1_rpm: int
    shift_stage_2_rpm: int
    redline_rpm: int
    updated_at: str
