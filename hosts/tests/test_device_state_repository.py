"""Persistence behavior for the simulated button pad."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from e87canbus.adapters.sqlite_button_profiles import SqliteButtonProfileRepository
from e87canbus.adapters.sqlite_database import SqliteApplicationDatabase
from e87canbus.adapters.sqlite_device_state import (
    DeviceRoleMismatchError,
    DeviceStateStorageError,
    SqliteDeviceStateRepository,
)
from e87canbus.adapters.sqlite_settings import SqliteApplicationSettingsRepository
from e87canbus.api.auth import DeviceRole
from e87canbus.api.main import create_app
from e87canbus.api.models.button_pad import (
    ButtonPadDeviceStatus,
    ButtonPadScene,
    ButtonPadStatus,
    SceneButton,
)
from e87canbus.domain.buttons.profiles import BUILT_IN_BUTTON_PROFILE
from e87canbus.domain.settings.values import DEFAULT_APPLICATION_SETTINGS, SpeedUnit
from migration_test_support import rewind_application_database
from pydantic import ValidationError

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
ROLE = DeviceRole.BUTTON_PAD


def scene(brightness: int = 255) -> ButtonPadScene:
    return ButtonPadScene(
        schema_version=1,
        brightness=brightness,
        buttons=[SceneButton(assigned=False, colour=[0, 0, 0], animation=None) for _ in range(16)],
    )


def repository(path: Path, *, now: datetime = NOW) -> SqliteDeviceStateRepository:
    database = SqliteApplicationDatabase(path, clock=lambda: now)
    database.initialize()
    return SqliteDeviceStateRepository(database, clock=lambda: now)


def test_configuration_generation_and_restart(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    device_id = str(uuid4())
    first = repository(path).get_or_create_configuration(device_id, ROLE, scene())
    assert first.generation == 0
    assert repository(path).get_or_create_configuration(device_id, ROLE, scene(40)) == first
    assert repository(path).replace_configuration_if_changed(device_id, ROLE, scene()) == first

    changed = repository(path).replace_configuration_if_changed(device_id, ROLE, scene(40))
    assert changed.generation == 1
    assert repository(path).replace_configuration_if_changed(device_id, ROLE, scene(40)) == changed
    assert repository(path).get_configuration(device_id, ROLE) == changed


def test_concurrent_first_contact_and_replacement(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    device_id = str(uuid4())
    state = repository(path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        first = list(
            pool.map(
                lambda _: state.get_or_create_configuration(device_id, ROLE, scene()), range(8)
            )
        )
    assert all(result.generation == 0 for result in first)
    with ThreadPoolExecutor(max_workers=8) as pool:
        changed = list(
            pool.map(
                lambda _: state.replace_configuration_if_changed(device_id, ROLE, scene(40)),
                range(8),
            )
        )
    assert all(result.generation == 1 for result in changed)


def test_status_replaces_last_report_and_uses_coordinator_clock(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    device_id = str(uuid4())
    first = repository(path).upsert_status(
        device_id,
        ROLE,
        ButtonPadStatus(
            status_version=1,
            applied_configuration_generation=0,
            configuration_error=None,
            device=ButtonPadDeviceStatus(),
        ),
    )
    later = NOW + timedelta(minutes=5)
    second = repository(path, now=later).upsert_status(
        device_id,
        ROLE,
        ButtonPadStatus(
            status_version=1,
            applied_configuration_generation=1,
            configuration_error="invalid scene",
            device=ButtonPadDeviceStatus(),
        ),
    )
    assert first.received_at_utc == "2026-09-24T12:00:00.000000Z"
    assert second.received_at_utc == "2026-09-24T12:05:00.000000Z"
    assert repository(path).get_status(device_id, ROLE) == second


def test_button_pad_status_rejects_role_specific_fields() -> None:
    with pytest.raises(ValidationError):
        ButtonPadDeviceStatus.model_validate({"temperature": 42})


def test_role_mismatch_and_storage_errors(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    device_id = str(uuid4())
    state = repository(path)
    state.get_or_create_configuration(device_id, ROLE, scene())
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE device_configurations SET role = ? WHERE device_id = ?",
            (DeviceRole.SERVOTRONIC_CONTROLLER.value, device_id),
        )
    with pytest.raises(DeviceRoleMismatchError):
        state.get_or_create_configuration(device_id, ROLE, scene())
    with pytest.raises(DeviceRoleMismatchError):
        state.upsert_status(
            device_id,
            ROLE,
            ButtonPadStatus(
                status_version=1,
                applied_configuration_generation=0,
                configuration_error=None,
                device=ButtonPadDeviceStatus(),
            ),
        )
    with pytest.raises(DeviceStateStorageError):
        SqliteDeviceStateRepository(tmp_path / "missing.sqlite3").get_configuration(device_id, ROLE)


def test_upgrade_from_version_nine_preserves_existing_data(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    database = SqliteApplicationDatabase(path, clock=lambda: NOW)
    database.initialize()
    profiles = SqliteButtonProfileRepository(database, clock=lambda: NOW)
    profile = profiles.create_profile("Keep me", BUILT_IN_BUTTON_PROFILE)
    settings = SqliteApplicationSettingsRepository(database, clock=lambda: NOW)
    edited_settings = settings.update_settings(
        1, replace(DEFAULT_APPLICATION_SETTINGS.editable_values(), speed_unit=SpeedUnit.KMH)
    )
    with database.connect() as connection:
        rewind_application_database(connection, 9)
    database.initialize()
    assert profiles.get_profile(profile.profile_id) == profile
    assert settings.get_settings() == edited_settings
    assert repository(path).get_or_create_configuration(str(uuid4()), ROLE, scene()).generation == 0


def test_app_exposes_device_state_repository(tmp_path: Path) -> None:
    app = create_app(profile_database_path=tmp_path / "state.sqlite3")
    assert isinstance(app.state.device_state_repository, SqliteDeviceStateRepository)
