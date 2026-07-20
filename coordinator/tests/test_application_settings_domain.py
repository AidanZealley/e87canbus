from dataclasses import fields, replace

import pytest
from e87canbus.features.application_settings import (
    DEFAULT_APPLICATION_SETTINGS,
    ApplicationSettings,
    ApplicationSettingsUpdate,
    SpeedUnit,
    TemperatureUnit,
    validate_expected_revision,
)


def test_default_settings_are_valid_stable_and_have_no_theme() -> None:
    assert (
        ApplicationSettings(
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
            updated_at="1970-01-01T00:00:00.000000Z",
        )
        == DEFAULT_APPLICATION_SETTINGS
    )
    assert "theme" not in {field.name for field in fields(ApplicationSettings)}
    assert "theme" not in {field.name for field in fields(ApplicationSettingsUpdate)}


@pytest.mark.parametrize("speed_unit", ["mph", "knots", None])
def test_speed_unit_must_be_an_enum(speed_unit: object) -> None:
    with pytest.raises(ValueError, match="SpeedUnit"):
        replace(DEFAULT_APPLICATION_SETTINGS.editable_values(), speed_unit=speed_unit)


@pytest.mark.parametrize("temperature_unit", ["c", "kelvin", None])
def test_temperature_unit_must_be_an_enum(temperature_unit: object) -> None:
    with pytest.raises(ValueError, match="TemperatureUnit"):
        replace(
            DEFAULT_APPLICATION_SETTINGS.editable_values(),
            temperature_unit=temperature_unit,
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("oil_warning_c", float("nan")),
        ("oil_warning_c", float("inf")),
        ("oil_warning_c", True),
        ("oil_warning_c", -40.1),
        ("oil_critical_c", 250.1),
        ("coolant_warning_c", float("-inf")),
        ("coolant_critical_c", "115"),
    ],
)
def test_temperatures_must_be_finite_numbers_in_range(field_name: str, value: object) -> None:
    with pytest.raises(ValueError):
        replace(DEFAULT_APPLICATION_SETTINGS.editable_values(), **{field_name: value})


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"oil_warning_c": 135.0}, "oil_warning_c"),
        ({"oil_warning_c": 136.0}, "oil_warning_c"),
        ({"coolant_warning_c": 115.0}, "coolant_warning_c"),
        ({"coolant_warning_c": 116.0}, "coolant_warning_c"),
    ],
)
def test_warning_thresholds_must_be_below_critical(changes: dict[str, float], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        replace(DEFAULT_APPLICATION_SETTINGS.editable_values(), **changes)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("shift_stage_1_rpm", True),
        ("shift_stage_1_rpm", 6800.0),
        ("shift_stage_1_rpm", 999),
        ("shift_stage_2_rpm", 12001),
        ("redline_rpm", "7200"),
    ],
)
def test_rpm_values_must_be_ordinary_integers_in_range(field_name: str, value: object) -> None:
    with pytest.raises(ValueError):
        replace(DEFAULT_APPLICATION_SETTINGS.editable_values(), **{field_name: value})


@pytest.mark.parametrize(
    "changes",
    [
        {"shift_stage_1_rpm": 7000},
        {"shift_stage_1_rpm": 7100},
        {"shift_stage_2_rpm": 7200},
        {"shift_stage_2_rpm": 7300},
    ],
)
def test_rpm_stages_are_strictly_ordered(changes: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="shift_stage_1_rpm"):
        replace(DEFAULT_APPLICATION_SETTINGS.editable_values(), **changes)


@pytest.mark.parametrize("revision", [True, 0, -1, 1.0])
def test_settings_revision_must_be_a_positive_integer(revision: object) -> None:
    with pytest.raises(ValueError, match="revision"):
        replace(DEFAULT_APPLICATION_SETTINGS, revision=revision)


@pytest.mark.parametrize("revision", [True, 0, -1, 1.0])
def test_expected_revision_must_be_a_positive_integer(revision: object) -> None:
    with pytest.raises(ValueError, match="expected_revision"):
        validate_expected_revision(revision)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "updated_at",
    [
        "2026-07-14T12:30:00Z",
        "2026-07-14T12:30:00.000000+00:00",
        "2026-07-14T13:30:00.000000+01:00",
        "not-a-timestamp",
    ],
)
def test_updated_at_must_use_canonical_utc_text(updated_at: str) -> None:
    with pytest.raises(ValueError, match="canonical UTC"):
        replace(DEFAULT_APPLICATION_SETTINGS, updated_at=updated_at)
