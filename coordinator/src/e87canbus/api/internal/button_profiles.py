"""Button-profile persistence, translation, and runtime installation use cases."""

from __future__ import annotations

from fastapi import FastAPI

from e87canbus.api.errors import ApiProblem
from e87canbus.api.internal.commands import submit_command
from e87canbus.api.internal.profiles import repository_operation
from e87canbus.api.internal.resources import publish_resource_change
from e87canbus.api.models.button_profiles import (
    ButtonProfileDefinitionRequest,
    ButtonProfileResponse,
    CreateButtonProfileRequest,
    UpdateButtonProfileRequest,
)
from e87canbus.config import SteeringConfig
from e87canbus.domain.button_commands import encode_button_command
from e87canbus.domain.button_profiles import (
    ButtonProfileDefinition,
    ButtonProfileRepository,
    StoredButtonProfile,
    decode_button_profile,
    validate_button_profile_for,
    validate_button_profile_id,
)
from e87canbus.kernel import ActivateButtonProfile


def definition_from_request(
    request: ButtonProfileDefinitionRequest,
    steering_config: SteeringConfig,
) -> ButtonProfileDefinition:
    """Hand the shape-checked request body to the single domain decoder.

    Pydantic has already rejected unknown tags and stray fields; dumping the model back
    to plain JSON keeps the tag vocabulary itself defined in exactly one place, so an
    eighth button command cannot be accepted here and then be undecodable from storage.
    The configuration check that follows rejects values this vehicle cannot run, which
    no static schema can express - without it they would only fail on the first press.
    """

    try:
        definition = decode_button_profile(request.model_dump(mode="json"))
        validate_button_profile_for(definition, steering_config)
    except (TypeError, ValueError) as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc
    return definition


def response(profile: StoredButtonProfile) -> ButtonProfileResponse:
    return ButtonProfileResponse.model_validate(
        {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "revision": profile.revision,
            "definition": {
                "schema_version": profile.definition.schema_version,
                "slots": [
                    None if command is None else encode_button_command(command)
                    for command in profile.definition.slots
                ],
            },
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }
    )


async def list_profiles(repository: ButtonProfileRepository) -> list[ButtonProfileResponse]:
    return [response(profile) for profile in await repository_operation(repository.list_profiles)]


async def get_saved_profile(repository: ButtonProfileRepository) -> ButtonProfileResponse:
    return response(await repository_operation(repository.get_selected_profile))


async def get_profile(
    repository: ButtonProfileRepository, profile_id: str
) -> ButtonProfileResponse:
    _validate_id(profile_id)
    profile = await repository_operation(lambda: repository.get_profile(profile_id))
    if profile is None:
        raise ApiProblem(404, "profile_not_found", f"button profile not found: {profile_id}")
    return response(profile)


async def create_profile(
    app: FastAPI, repository: ButtonProfileRepository, request: CreateButtonProfileRequest
) -> ButtonProfileResponse:
    definition = (
        None
        if request.definition is None
        else definition_from_request(request.definition, _steering_config(app))
    )
    async with app.state.button_profile_mutation_lock:
        profile = await repository_operation(
            lambda: repository.create_profile(request.name, definition)
        )
        await _publish(app, profile)
        return response(profile)


async def update_profile(
    app: FastAPI,
    repository: ButtonProfileRepository,
    profile_id: str,
    request: UpdateButtonProfileRequest,
) -> ButtonProfileResponse:
    _validate_id(profile_id)
    definition = definition_from_request(request.definition, _steering_config(app))
    async with app.state.button_profile_mutation_lock:
        profile = await repository_operation(
            lambda: repository.update_profile(
                profile_id,
                request.expected_revision,
                request.name,
                definition,
            )
        )
        await _install_updated_profile(app, repository, profile)
        await _publish(app, profile)
        return response(profile)


async def delete_profile(
    app: FastAPI,
    repository: ButtonProfileRepository,
    profile_id: str,
    expected_revision: int,
) -> None:
    _validate_id(profile_id)
    async with app.state.button_profile_mutation_lock:
        await repository_operation(lambda: repository.delete_profile(profile_id, expected_revision))
        await publish_resource_change(
            app, resource="button_profile", resource_id=profile_id, revision=expected_revision
        )


async def _install_updated_profile(
    app: FastAPI,
    repository: ButtonProfileRepository,
    profile: StoredButtonProfile,
) -> None:
    """Make a successful edit the runtime and startup profile immediately."""

    await submit_command(
        app,
        ActivateButtonProfile(
            profile.as_active(),
            saved_profile_revision=profile.revision,
            requested_at=app.state.monotonic_clock(),
        ),
    )
    # Runtime installation cannot share SQLite's transaction. If selection persistence
    # fails, retain the safely installed runtime, report failure, and mark persistence
    # unhealthy; startup will continue to use the prior selection.
    try:
        await repository_operation(
            lambda: repository.select_profile(profile.profile_id, profile.revision)
        )
    except ApiProblem as exc:
        if exc.code == "profile_storage_error":
            app.state.controller_service.mark_persistence_fault(exc.message)
        raise


async def _publish(app: FastAPI, profile: StoredButtonProfile) -> None:
    await publish_resource_change(
        app,
        resource="button_profile",
        resource_id=profile.profile_id,
        revision=profile.revision,
    )


def _steering_config(app: FastAPI) -> SteeringConfig:
    config: SteeringConfig = app.state.controller_service.config.steering
    return config


def _validate_id(profile_id: str) -> None:
    try:
        validate_button_profile_id(profile_id)
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc
