from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from e87canbus.api.main import create_app
from e87canbus.features.application_settings import (
    DEFAULT_APPLICATION_SETTINGS,
    ApplicationSettings,
    ApplicationSettingsUpdate,
)
from e87canbus.features.profile_repository import SteeringProfileRepository
from e87canbus.features.settings_repository import (
    ApplicationSettingsRepository,
    SettingsRevisionConflictError,
    SettingsStorageError,
)
from fastapi.testclient import TestClient


def settings_json(settings: ApplicationSettings = DEFAULT_APPLICATION_SETTINGS) -> dict[str, Any]:
    return {
        "revision": settings.revision,
        "speed_unit": settings.speed_unit.value,
        "temperature_unit": settings.temperature_unit.value,
        "oil_warning_c": settings.oil_warning_c,
        "oil_critical_c": settings.oil_critical_c,
        "coolant_warning_c": settings.coolant_warning_c,
        "coolant_critical_c": settings.coolant_critical_c,
        "shift_stage_1_rpm": settings.shift_stage_1_rpm,
        "shift_stage_2_rpm": settings.shift_stage_2_rpm,
        "redline_rpm": settings.redline_rpm,
        "updated_at": settings.updated_at,
    }


def update_json(
    settings: ApplicationSettings = DEFAULT_APPLICATION_SETTINGS,
    *,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    value = settings_json(settings)
    value.pop("revision")
    value.pop("updated_at")
    value["expected_revision"] = expected_revision or settings.revision
    return value


class MemorySettingsRepository:
    def __init__(self) -> None:
        self.settings = DEFAULT_APPLICATION_SETTINGS
        self.error: Exception | None = None

    def get_settings(self) -> ApplicationSettings:
        if self.error is not None:
            raise self.error
        return self.settings

    def update_settings(
        self,
        expected_revision: int,
        candidate: ApplicationSettingsUpdate,
    ) -> ApplicationSettings:
        if self.error is not None:
            raise self.error
        if expected_revision != self.settings.revision:
            raise SettingsRevisionConflictError(expected_revision, self.settings.revision)
        self.settings = ApplicationSettings(
            revision=self.settings.revision + 1,
            **candidate.__dict__,
            updated_at="2026-07-14T12:30:00.000000Z",
        )
        return self.settings


class RecordingManager:
    def __init__(self) -> None:
        self.broadcasts: list[Any] = []

    async def broadcast(self, events: Any) -> None:
        self.broadcasts.append(events)


def injected_app(repository: ApplicationSettingsRepository):
    return create_app(
        profile_repository=cast(SteeringProfileRepository, object()),
        settings_repository=repository,
    )


def test_get_and_put_serialize_complete_authoritative_document() -> None:
    repository = MemorySettingsRepository()
    app = injected_app(repository)
    manager = RecordingManager()
    app.state.manager = manager
    with TestClient(app) as client:
        fetched = client.get("/api/settings")
        payload = update_json()
        payload["speed_unit"] = "kmh"
        updated = client.put("/api/settings", json=payload)

    assert fetched.status_code == 200
    assert fetched.json() == settings_json()
    assert updated.status_code == 200
    assert updated.json() == settings_json(repository.settings)
    assert updated.json()["revision"] == 2
    assert manager.broadcasts == [({"type": "application_settings_changed"},)]


@pytest.mark.parametrize(
    "change",
    [
        {"speed_unit": "knots"},
        {"oil_warning_c": 140.0},
        {"shift_stage_1_rpm": True},
        {"redline_rpm": 7000},
        {"theme": "dark"},
    ],
)
def test_invalid_request_or_domain_value_is_422_and_not_broadcast(
    change: dict[str, Any],
) -> None:
    repository = MemorySettingsRepository()
    app = injected_app(repository)
    manager = RecordingManager()
    app.state.manager = manager
    payload = {**update_json(), **change}

    with TestClient(app) as client:
        response = client.put("/api/settings", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert repository.settings == DEFAULT_APPLICATION_SETTINGS
    assert manager.broadcasts == []


def test_conflict_includes_current_revision_and_does_not_broadcast() -> None:
    repository = MemorySettingsRepository()
    repository.settings = replace(DEFAULT_APPLICATION_SETTINGS, revision=3)
    app = injected_app(repository)
    manager = RecordingManager()
    app.state.manager = manager

    with TestClient(app) as client:
        response = client.put("/api/settings", json=update_json(expected_revision=1))

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "settings_revision_conflict",
        "message": "application settings are at revision 3, not 1",
        "current_revision": 3,
    }
    assert manager.broadcasts == []


@pytest.mark.parametrize("method", ["get", "put"])
def test_storage_failure_is_typed_503_and_not_broadcast(method: str) -> None:
    repository = MemorySettingsRepository()
    repository.error = SettingsStorageError("database unavailable")
    app = injected_app(repository)
    manager = RecordingManager()
    app.state.manager = manager

    with TestClient(app) as client:
        response = getattr(client, method)(
            "/api/settings",
            **({"json": update_json()} if method == "put" else {}),
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "settings_storage_error"
    assert manager.broadcasts == []


def test_settings_persist_across_app_restart(tmp_path: Path) -> None:
    path = tmp_path / "application.sqlite3"
    with TestClient(create_app(profile_database_path=path)) as client:
        payload = update_json()
        payload["oil_warning_c"] = 124.5
        committed = client.put("/api/settings", json=payload)
        assert committed.status_code == 200

    with TestClient(create_app(profile_database_path=path)) as restarted:
        fetched = restarted.get("/api/settings")

    assert fetched.status_code == 200
    assert fetched.json() == committed.json()


def test_independently_injected_repository_is_used() -> None:
    repository = MemorySettingsRepository()

    with TestClient(injected_app(repository)) as client:
        assert client.get("/api/settings").json() == settings_json(repository.settings)
