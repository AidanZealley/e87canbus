"""Button-profile persistence, translation, and activation use cases."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar, assert_never

from fastapi import FastAPI

from e87canbus.api.errors import ApiProblem
from e87canbus.api.internal.commands import submit_command
from e87canbus.api.internal.resources import publish_resource_change
from e87canbus.api.models.button_profiles import (
    ActivateButtonProfileRequest,
    ButtonProfileCommand,
    ButtonProfileDefinitionRequest,
    ButtonProfileResponse,
    CreateButtonProfileRequest,
    UpdateButtonProfileRequest,
)
from e87canbus.api.models.commands import CommandAcknowledgement
from e87canbus.domain.button_bindings import button_binding_profile_from_definition
from e87canbus.domain.button_profile_repository import (
    ButtonProfileNameConflictError,
    ButtonProfileNotFoundError,
    ButtonProfileProtectedError,
    ButtonProfileRepository,
    ButtonProfileRevisionConflictError,
    ButtonProfileStorageError,
)
from e87canbus.domain.button_profiles import (
    ButtonProfileDefinition,
    StoredButtonProfile,
    UserButtonIntent,
    validate_button_profile_id,
)
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    StartHighBeamStrobe,
    ToggleAutomaticAssistance,
    ToggleMaximumAssistance,
)
from e87canbus.domain.state import SteeringMode
from e87canbus.kernel import ActivateButtonProfile

T = TypeVar("T")


def _intent(command: ButtonProfileCommand) -> UserButtonIntent:
    match command.type:
        case "select_steering_mode":
            return SelectSteeringMode(SteeringMode(command.mode))
        case "toggle_automatic_assistance":
            return ToggleAutomaticAssistance()
        case "adjust_manual_assistance":
            return AdjustManualAssistance(command.delta)
        case "set_manual_assistance_level":
            return SetManualAssistanceLevel(command.level)
        case "set_maximum_assistance":
            return SetMaximumAssistance(command.enabled)
        case "toggle_maximum_assistance":
            return ToggleMaximumAssistance()
        case "start_high_beam_strobe":
            return StartHighBeamStrobe()
        case _:
            assert_never(command.type)


def definition_from_request(request: ButtonProfileDefinitionRequest) -> ButtonProfileDefinition:
    try:
        return ButtonProfileDefinition(
            request.schema_version,
            tuple(None if command is None else _intent(command) for command in request.slots),
        )
    except (TypeError, ValueError) as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc


def _command(intent: UserButtonIntent) -> dict[str, Any]:
    match intent:
        case SelectSteeringMode(mode=mode):
            return {"type": "select_steering_mode", "mode": mode.value}
        case ToggleAutomaticAssistance():
            return {"type": "toggle_automatic_assistance"}
        case AdjustManualAssistance(delta=delta):
            return {"type": "adjust_manual_assistance", "delta": delta}
        case SetManualAssistanceLevel(level=level):
            return {"type": "set_manual_assistance_level", "level": level}
        case SetMaximumAssistance(enabled=enabled):
            return {"type": "set_maximum_assistance", "enabled": enabled}
        case ToggleMaximumAssistance():
            return {"type": "toggle_maximum_assistance"}
        case StartHighBeamStrobe():
            return {"type": "start_high_beam_strobe"}
        case _:
            assert_never(intent)


def response(profile: StoredButtonProfile) -> ButtonProfileResponse:
    return ButtonProfileResponse.model_validate(
        {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "revision": profile.revision,
            "definition": {
                "schema_version": profile.definition.schema_version,
                "slots": [
                    None if intent is None else _command(intent)
                    for intent in profile.definition.slots
                ],
            },
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }
    )


async def list_profiles(repository: ButtonProfileRepository) -> list[ButtonProfileResponse]:
    return [response(profile) for profile in await _repository(repository.list_profiles)]


async def get_saved_profile(repository: ButtonProfileRepository) -> ButtonProfileResponse:
    return response(await _repository(repository.get_selected_profile))


async def get_profile(
    repository: ButtonProfileRepository, profile_id: str
) -> ButtonProfileResponse:
    _validate_id(profile_id)
    profile = await _repository(lambda: repository.get_profile(profile_id))
    if profile is None:
        raise ApiProblem(404, "profile_not_found", f"button profile not found: {profile_id}")
    return response(profile)


async def create_profile(
    app: FastAPI, repository: ButtonProfileRepository, request: CreateButtonProfileRequest
) -> ButtonProfileResponse:
    async with app.state.button_profile_mutation_lock:
        definition = (
            None if request.definition is None else definition_from_request(request.definition)
        )
        profile = await _repository(lambda: repository.create_profile(request.name, definition))
        await _publish(app, profile)
        return response(profile)


async def update_profile(
    app: FastAPI,
    repository: ButtonProfileRepository,
    profile_id: str,
    request: UpdateButtonProfileRequest,
) -> ButtonProfileResponse:
    async with app.state.button_profile_mutation_lock:
        _validate_id(profile_id)
        profile = await _repository(
            lambda: repository.update_profile(
                profile_id,
                request.expected_revision,
                request.name,
                definition_from_request(request.definition),
            )
        )
        await _publish(app, profile)
        return response(profile)


async def delete_profile(
    app: FastAPI,
    repository: ButtonProfileRepository,
    profile_id: str,
    expected_revision: int,
) -> None:
    async with app.state.button_profile_mutation_lock:
        _validate_id(profile_id)
        await _repository(lambda: repository.delete_profile(profile_id, expected_revision))
        await publish_resource_change(
            app, resource="button_profile", resource_id=profile_id, revision=expected_revision
        )


async def activate_profile(
    app: FastAPI,
    repository: ButtonProfileRepository,
    request: ActivateButtonProfileRequest,
) -> CommandAcknowledgement:
    async with app.state.button_profile_mutation_lock:
        _validate_id(request.profile_id)
        profile = await _repository(lambda: repository.get_profile(request.profile_id))
        if profile is None:
            raise ApiProblem(
                404, "profile_not_found", f"button profile not found: {request.profile_id}"
            )
        if profile.revision != request.expected_revision:
            raise ApiProblem(
                409,
                "profile_revision_conflict",
                f"button profile {profile.profile_id} is at revision {profile.revision}, "
                f"not {request.expected_revision}",
                current_revision=profile.revision,
            )
        compiled = button_binding_profile_from_definition(profile.definition, profile.profile_id)
        acknowledgement = await submit_command(
            app,
            ActivateButtonProfile(
                compiled,
                saved_profile_revision=profile.revision,
                requested_at=app.state.monotonic_clock(),
            ),
        )
        # Runtime activation cannot share SQLite's transaction. If persistence fails,
        # retain the safely activated runtime, report failure, and explicitly mark
        # persistence unhealthy; startup will continue to use the prior selection.
        try:
            await _repository(
                lambda: repository.select_profile(profile.profile_id, profile.revision)
            )
        except ApiProblem as exc:
            if exc.code == "profile_storage_error":
                app.state.controller_service.mark_persistence_fault(exc.message)
            raise
        await _publish(app, profile)
        return acknowledgement


async def _publish(app: FastAPI, profile: StoredButtonProfile) -> None:
    await publish_resource_change(
        app,
        resource="button_profile",
        resource_id=profile.profile_id,
        revision=profile.revision,
    )


async def _repository(operation: Callable[[], T]) -> T:
    try:
        return await asyncio.to_thread(operation)
    except ButtonProfileRevisionConflictError as exc:
        raise ApiProblem(
            409, "profile_revision_conflict", str(exc), current_revision=exc.actual_revision
        ) from exc
    except ButtonProfileNameConflictError as exc:
        raise ApiProblem(409, "profile_name_conflict", str(exc)) from exc
    except ButtonProfileProtectedError as exc:
        raise ApiProblem(409, "profile_protected", str(exc)) from exc
    except ButtonProfileNotFoundError as exc:
        raise ApiProblem(404, "profile_not_found", str(exc)) from exc
    except ButtonProfileStorageError as exc:
        raise ApiProblem(503, "profile_storage_error", str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc


def _validate_id(profile_id: str) -> None:
    try:
        validate_button_profile_id(profile_id)
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc
