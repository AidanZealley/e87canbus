"""Framework-independent application-settings values and validation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from e87canbus.features.timestamps import validate_canonical_utc_timestamp

MIN_TEMPERATURE_C = -40.0
MAX_TEMPERATURE_C = 250.0
MIN_RPM = 1000
MAX_RPM = 12000
DEFAULT_SETTINGS_UPDATED_AT = "1970-01-01T00:00:00.000000Z"


class SpeedUnit(StrEnum):
    MPH = "mph"
    KMH = "kmh"


class TemperatureUnit(StrEnum):
    CELSIUS = "c"
    FAHRENHEIT = "f"


@dataclass(frozen=True)
class ApplicationSettingsUpdate:
    """Complete editable settings submitted as one revisioned candidate."""

    speed_unit: SpeedUnit
    temperature_unit: TemperatureUnit
    oil_warning_c: float
    oil_critical_c: float
    coolant_warning_c: float
    coolant_critical_c: float
    shift_stage_1_rpm: int
    shift_stage_2_rpm: int
    redline_rpm: int

    def __post_init__(self) -> None:
        validate_application_settings_update(self)


@dataclass(frozen=True)
class ApplicationSettings:
    """The complete authoritative, immutable application-settings document."""

    revision: int
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

    def __post_init__(self) -> None:
        validate_application_settings(self)

    def editable_values(self) -> ApplicationSettingsUpdate:
        return ApplicationSettingsUpdate(
            speed_unit=self.speed_unit,
            temperature_unit=self.temperature_unit,
            oil_warning_c=self.oil_warning_c,
            oil_critical_c=self.oil_critical_c,
            coolant_warning_c=self.coolant_warning_c,
            coolant_critical_c=self.coolant_critical_c,
            shift_stage_1_rpm=self.shift_stage_1_rpm,
            shift_stage_2_rpm=self.shift_stage_2_rpm,
            redline_rpm=self.redline_rpm,
        )


def validate_application_settings_update(candidate: ApplicationSettingsUpdate) -> None:
    if not isinstance(candidate.speed_unit, SpeedUnit):
        raise ValueError("speed_unit must be a supported SpeedUnit value")
    if not isinstance(candidate.temperature_unit, TemperatureUnit):
        raise ValueError("temperature_unit must be a supported TemperatureUnit value")

    temperatures = {
        "oil_warning_c": candidate.oil_warning_c,
        "oil_critical_c": candidate.oil_critical_c,
        "coolant_warning_c": candidate.coolant_warning_c,
        "coolant_critical_c": candidate.coolant_critical_c,
    }
    for field_name, value in temperatures.items():
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{field_name} must be a finite number")
        if not MIN_TEMPERATURE_C <= value <= MAX_TEMPERATURE_C:
            raise ValueError(
                f"{field_name} must be between {MIN_TEMPERATURE_C:g} and "
                f"{MAX_TEMPERATURE_C:g} C"
            )
    if candidate.oil_warning_c >= candidate.oil_critical_c:
        raise ValueError("oil_warning_c must be below oil_critical_c")
    if candidate.coolant_warning_c >= candidate.coolant_critical_c:
        raise ValueError("coolant_warning_c must be below coolant_critical_c")

    rpm_values = {
        "shift_stage_1_rpm": candidate.shift_stage_1_rpm,
        "shift_stage_2_rpm": candidate.shift_stage_2_rpm,
        "redline_rpm": candidate.redline_rpm,
    }
    for field_name, value in rpm_values.items():
        if type(value) is not int:
            raise ValueError(f"{field_name} must be an integer")
        if not MIN_RPM <= value <= MAX_RPM:
            raise ValueError(f"{field_name} must be between {MIN_RPM} and {MAX_RPM}")
    if not (
        candidate.shift_stage_1_rpm
        < candidate.shift_stage_2_rpm
        < candidate.redline_rpm
    ):
        raise ValueError(
            "shift_stage_1_rpm must be below shift_stage_2_rpm and redline_rpm"
        )


def validate_application_settings(settings: ApplicationSettings) -> None:
    if type(settings.revision) is not int or settings.revision < 1:
        raise ValueError("settings revision must be a positive integer")
    validate_application_settings_update(settings.editable_values())
    validate_canonical_utc_timestamp(settings.updated_at, "updated_at")


def validate_expected_revision(expected_revision: int) -> None:
    if type(expected_revision) is not int or expected_revision < 1:
        raise ValueError("expected_revision must be a positive integer")


DEFAULT_APPLICATION_SETTINGS = ApplicationSettings(
    revision=1,
    speed_unit=SpeedUnit.MPH,
    temperature_unit=TemperatureUnit.CELSIUS,
    oil_warning_c=125.0,
    oil_critical_c=135.0,
    coolant_warning_c=105.0,
    coolant_critical_c=115.0,
    shift_stage_1_rpm=6800,
    shift_stage_2_rpm=7000,
    redline_rpm=7200,
    updated_at=DEFAULT_SETTINGS_UPDATED_AT,
)
