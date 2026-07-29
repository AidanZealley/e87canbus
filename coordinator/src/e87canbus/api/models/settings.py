"""Application-settings HTTP request and response models."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from e87canbus.domain.settings.values import (
    DASHBOARD_ID_PATTERN,
    MAX_DASHBOARD_ID_LENGTH,
    MAX_RPM,
    MAX_TEMPERATURE_C,
    MIN_RPM,
    MIN_TEMPERATURE_C,
    SpeedUnit,
    TemperatureUnit,
)


# Constrained by shape rather than by a list of known dashboards: the display
# owns that catalog, so new dashboards ship without touching the coordinator.
def dashboard_id_field() -> Any:
    return Field(
        min_length=1,
        max_length=MAX_DASHBOARD_ID_LENGTH,
        pattern=DASHBOARD_ID_PATTERN.pattern,
    )


class UpdateApplicationSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_revision: int = Field(ge=1)
    speed_unit: Literal["mph", "kmh"]
    temperature_unit: Literal["c", "f"]
    oil_operating_c: float = Field(ge=MIN_TEMPERATURE_C, le=MAX_TEMPERATURE_C)
    oil_warning_c: float = Field(ge=MIN_TEMPERATURE_C, le=MAX_TEMPERATURE_C)
    oil_critical_c: float = Field(ge=MIN_TEMPERATURE_C, le=MAX_TEMPERATURE_C)
    coolant_operating_c: float = Field(ge=MIN_TEMPERATURE_C, le=MAX_TEMPERATURE_C)
    coolant_warning_c: float = Field(ge=MIN_TEMPERATURE_C, le=MAX_TEMPERATURE_C)
    coolant_critical_c: float = Field(ge=MIN_TEMPERATURE_C, le=MAX_TEMPERATURE_C)
    shift_stage_1_rpm: int = Field(ge=MIN_RPM, le=MAX_RPM)
    shift_stage_2_rpm: int = Field(ge=MIN_RPM, le=MAX_RPM)
    redline_rpm: int = Field(ge=MIN_RPM, le=MAX_RPM)
    dashboard_id: str = dashboard_id_field()


class ApplicationSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    revision: int = Field(ge=1)
    speed_unit: SpeedUnit
    temperature_unit: TemperatureUnit
    oil_operating_c: float
    oil_warning_c: float
    oil_critical_c: float
    coolant_operating_c: float
    coolant_warning_c: float
    coolant_critical_c: float
    shift_stage_1_rpm: int
    shift_stage_2_rpm: int
    redline_rpm: int
    dashboard_id: str = dashboard_id_field()
    updated_at: str
