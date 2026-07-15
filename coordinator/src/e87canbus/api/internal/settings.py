"""Application-settings read/update and publication use cases."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import FastAPI

from e87canbus.api.errors import ApiProblem
from e87canbus.api.models.settings import UpdateApplicationSettingsRequest
from e87canbus.features.application_settings import (
    ApplicationSettings,
    ApplicationSettingsUpdate,
    SpeedUnit,
    TemperatureUnit,
)
from e87canbus.features.settings_repository import (
    ApplicationSettingsRepository,
    SettingsRevisionConflictError,
    SettingsStorageError,
)

T = TypeVar("T")


def settings_to_dict(settings: ApplicationSettings) -> dict[str, Any]:
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


def candidate_from_request(
    request: UpdateApplicationSettingsRequest,
) -> ApplicationSettingsUpdate:
    try:
        return ApplicationSettingsUpdate(
            speed_unit=SpeedUnit(request.speed_unit),
            temperature_unit=TemperatureUnit(request.temperature_unit),
            oil_warning_c=request.oil_warning_c,
            oil_critical_c=request.oil_critical_c,
            coolant_warning_c=request.coolant_warning_c,
            coolant_critical_c=request.coolant_critical_c,
            shift_stage_1_rpm=request.shift_stage_1_rpm,
            shift_stage_2_rpm=request.shift_stage_2_rpm,
            redline_rpm=request.redline_rpm,
        )
    except ValueError as error:
        raise ApiProblem(422, "validation_error", str(error)) from error


async def get_settings(repository: ApplicationSettingsRepository) -> dict[str, Any]:
    settings = await repository_operation(repository.get_settings)
    return settings_to_dict(settings)


async def update_settings(
    app: FastAPI,
    repository: ApplicationSettingsRepository,
    request: UpdateApplicationSettingsRequest,
) -> dict[str, Any]:
    candidate = candidate_from_request(request)
    committed = await repository_operation(
        lambda: repository.update_settings(request.expected_revision, candidate)
    )
    await app.state.manager.broadcast(({"type": "application_settings_changed"},))
    return settings_to_dict(committed)


async def repository_operation(operation: Callable[[], T]) -> T:
    try:
        return await asyncio.to_thread(operation)
    except SettingsRevisionConflictError as error:
        raise ApiProblem(
            409,
            "settings_revision_conflict",
            str(error),
            current_revision=error.current_revision,
        ) from error
    except SettingsStorageError as error:
        raise ApiProblem(503, "settings_storage_error", str(error)) from error
    except ValueError as error:
        raise ApiProblem(422, "validation_error", str(error)) from error
