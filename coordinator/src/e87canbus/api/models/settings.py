"""Strict request model for complete application-settings updates."""

from pydantic import BaseModel, ConfigDict


class UpdateApplicationSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_revision: int
    speed_unit: str
    temperature_unit: str
    oil_warning_c: float
    oil_critical_c: float
    coolant_warning_c: float
    coolant_critical_c: float
    shift_stage_1_rpm: int
    shift_stage_2_rpm: int
    redline_rpm: int
