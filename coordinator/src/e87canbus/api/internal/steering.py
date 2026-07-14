"""Steering-profile persistence and curve activation use cases."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import FastAPI

from e87canbus.api.errors import ApiProblem
from e87canbus.api.internal.simulation import submit
from e87canbus.api.models.steering import (
    ActivateCurveRequest,
    CreateProfileRequest,
    SteeringCurveDefinitionRequest,
    UpdateProfileRequest,
)
from e87canbus.features.profile_repository import (
    ProfileNameConflictError,
    ProfileNotFoundError,
    ProfileRevisionConflictError,
    SteeringProfileRepository,
    SteeringProfileStorageError,
)
from e87canbus.features.steering import (
    CurveInterpolation,
    SteeringCurveDefinition,
    SteeringCurvePoint,
    StoredSteeringProfile,
    validate_steering_profile_id,
)
from e87canbus.runtime import UnsupportedSteeringCurveInterpolation
from e87canbus.simulation.engine import (
    ActivateCurve,
    SimulationSessionFailed,
    SimulatorSnapshot,
)

T = TypeVar("T")


def definition_from_request(
    request: SteeringCurveDefinitionRequest,
) -> SteeringCurveDefinition:
    try:
        interpolation = CurveInterpolation(request.interpolation)
        return SteeringCurveDefinition(
            schema_version=request.schema_version,
            interpolation=interpolation,
            points=tuple(
                SteeringCurvePoint(point.speed_deci_kph, point.assistance_per_mille)
                for point in request.points
            ),
        )
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc


def definition_to_dict(definition: SteeringCurveDefinition) -> dict[str, Any]:
    return {
        "schema_version": definition.schema_version,
        "interpolation": definition.interpolation.value,
        "points": [
            {
                "speed_deci_kph": point.speed_deci_kph,
                "assistance_per_mille": point.assistance_per_mille,
            }
            for point in definition.points
        ],
    }


def profile_to_dict(profile: StoredSteeringProfile) -> dict[str, Any]:
    return {
        "profile_id": profile.profile_id,
        "name": profile.name,
        "revision": profile.revision,
        "definition": definition_to_dict(profile.definition),
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def curve_state_to_dict(snapshot: SimulatorSnapshot) -> dict[str, Any]:
    active = snapshot.application.active_steering_curve
    return {
        "definition": definition_to_dict(active.definition),
        "fingerprint": active.fingerprint,
        "activation_revision": active.activation_revision,
        "status": snapshot.application.steering_curve_activation_status.value,
        "saved_profile_id": active.saved_profile_id,
        "saved_profile_revision": active.saved_profile_revision,
        "supported_interpolations": [
            interpolation.value
            for interpolation in snapshot.application.supported_steering_curve_interpolations
        ],
    }


async def list_profiles(repository: SteeringProfileRepository) -> dict[str, Any]:
    profiles = await repository_operation(repository.list_profiles)
    return {"profiles": [profile_to_dict(profile) for profile in profiles]}


async def create_profile(
    app: FastAPI,
    repository: SteeringProfileRepository,
    request: CreateProfileRequest,
) -> dict[str, Any]:
    definition = definition_from_request(request.definition)
    profile = await repository_operation(
        lambda: repository.create_profile(request.name, definition)
    )
    await publish_profile_catalog_changed(app)
    return profile_to_dict(profile)


async def get_profile(
    repository: SteeringProfileRepository,
    profile_id: str,
) -> dict[str, Any]:
    validate_profile_id(profile_id)
    profile = await repository_operation(lambda: repository.get_profile(profile_id))
    if profile is None:
        raise ApiProblem(404, "profile_not_found", f"steering profile not found: {profile_id}")
    return profile_to_dict(profile)


async def update_profile(
    app: FastAPI,
    repository: SteeringProfileRepository,
    profile_id: str,
    request: UpdateProfileRequest,
) -> dict[str, Any]:
    validate_profile_id(profile_id)
    definition = definition_from_request(request.definition)
    profile = await repository_operation(
        lambda: repository.update_profile(
            profile_id,
            request.expected_revision,
            request.name,
            definition,
        )
    )
    await publish_profile_catalog_changed(app)
    return profile_to_dict(profile)


async def delete_profile(
    app: FastAPI,
    repository: SteeringProfileRepository,
    profile_id: str,
    expected_revision: int,
) -> None:
    validate_profile_id(profile_id)
    await repository_operation(lambda: repository.delete_profile(profile_id, expected_revision))
    await publish_profile_catalog_changed(app)


async def activate_curve(
    app: FastAPI,
    repository: SteeringProfileRepository,
    request: ActivateCurveRequest,
) -> dict[str, Any]:
    definition = definition_from_request(request.definition)
    saved_profile_id = request.saved_profile_id
    saved_profile_revision = request.saved_profile_revision
    if (saved_profile_id is None) != (saved_profile_revision is None):
        raise ApiProblem(
            422,
            "validation_error",
            "saved_profile_id and saved_profile_revision must be supplied together",
        )
    if saved_profile_id is not None:
        validate_profile_id(saved_profile_id, field_name="saved_profile_id")
        saved = await repository_operation(lambda: repository.get_profile(saved_profile_id))
        current_revision = None if saved is None else saved.revision
        if (
            saved is None
            or saved.revision != saved_profile_revision
            or saved.definition != definition
        ):
            raise ApiProblem(
                409,
                "saved_provenance_mismatch",
                "claimed saved profile provenance does not match the committed definition",
                current_revision=current_revision,
            )
    try:
        result = await submit(
            app,
            ActivateCurve(definition, saved_profile_id, saved_profile_revision),
        )
    except UnsupportedSteeringCurveInterpolation as exc:
        raise ApiProblem(
            409,
            "unsupported_interpolation",
            str(exc),
            supported_interpolations=tuple(item.value for item in exc.supported_interpolations),
        ) from exc
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc
    except SimulationSessionFailed as exc:
        raise ApiProblem(409, "simulation_session_failed", str(exc)) from exc
    if result.snapshot.fatal:
        raise ApiProblem(
            503,
            "activation_effect_failed",
            "curve activation committed but its immediate runtime effect failed",
        )
    return curve_state_to_dict(result.snapshot)


async def repository_operation(operation: Callable[[], T]) -> T:
    try:
        return await asyncio.to_thread(operation)
    except ProfileRevisionConflictError as exc:
        raise ApiProblem(
            409,
            "profile_revision_conflict",
            str(exc),
            current_revision=exc.actual_revision,
        ) from exc
    except ProfileNameConflictError as exc:
        raise ApiProblem(409, "profile_name_conflict", str(exc)) from exc
    except ProfileNotFoundError as exc:
        raise ApiProblem(404, "profile_not_found", str(exc)) from exc
    except SteeringProfileStorageError as exc:
        raise ApiProblem(503, "profile_storage_error", str(exc)) from exc
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc


def validate_profile_id(profile_id: str, *, field_name: str = "profile_id") -> None:
    try:
        validate_steering_profile_id(profile_id, field_name=field_name)
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc


async def publish_profile_catalog_changed(app: FastAPI) -> None:
    await app.state.manager.broadcast(({"type": "steering_profile_catalog_changed"},))
