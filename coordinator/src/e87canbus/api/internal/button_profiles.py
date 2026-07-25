"""Button-profile persistence, translation, and activation use cases."""

from __future__ import annotations

from fastapi import FastAPI

from e87canbus.api.errors import ApiProblem
from e87canbus.api.internal.commands import submit_command
from e87canbus.api.internal.profiles import repository_operation
from e87canbus.api.internal.resources import publish_resource_change
from e87canbus.api.models.button_profiles import (
    ActivateButtonProfileRequest,
    ButtonProfileDefinitionRequest,
    ButtonProfileResponse,
    CreateButtonProfileRequest,
    UpdateButtonProfileRequest,
)
from e87canbus.api.models.commands import CommandAcknowledgement
from e87canbus.domain.button_bindings import button_binding_profile_from_definition
from e87canbus.domain.button_profile_repository import ButtonProfileRepository
from e87canbus.domain.button_profiles import (
    ButtonProfileDefinition,
    StoredButtonProfile,
    decode_button_profile,
    encode_button_intent,
    validate_button_profile_id,
)
from e87canbus.kernel import ActivateButtonProfile


def definition_from_request(request: ButtonProfileDefinitionRequest) -> ButtonProfileDefinition:
    """Hand the shape-checked request body to the single domain decoder.

    Pydantic has already rejected unknown tags and stray fields; dumping the model back
    to plain JSON keeps the tag vocabulary itself defined in exactly one place, so an
    eighth button command cannot be accepted here and then be undecodable from storage.
    """

    try:
        return decode_button_profile(request.model_dump(mode="json"))
    except (TypeError, ValueError) as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc


def response(profile: StoredButtonProfile) -> ButtonProfileResponse:
    return ButtonProfileResponse.model_validate(
        {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "revision": profile.revision,
            "definition": {
                "schema_version": profile.definition.schema_version,
                "slots": [
                    None if intent is None else encode_button_intent(intent)
                    for intent in profile.definition.slots
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
    definition = None if request.definition is None else definition_from_request(request.definition)
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
    definition = definition_from_request(request.definition)
    async with app.state.button_profile_mutation_lock:
        profile = await repository_operation(
            lambda: repository.update_profile(
                profile_id,
                request.expected_revision,
                request.name,
                definition,
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
    _validate_id(profile_id)
    async with app.state.button_profile_mutation_lock:
        await repository_operation(lambda: repository.delete_profile(profile_id, expected_revision))
        await publish_resource_change(
            app, resource="button_profile", resource_id=profile_id, revision=expected_revision
        )


async def activate_profile(
    app: FastAPI,
    repository: ButtonProfileRepository,
    request: ActivateButtonProfileRequest,
) -> CommandAcknowledgement:
    _validate_id(request.profile_id)
    # The runtime submit stays inside the lock deliberately. It is the ordering point:
    # runtime activation and the stored selection must agree on which activation won, and
    # releasing the lock around the controller round-trip lets two activations interleave
    # so the pad runs profile A while storage records profile B. The wait is bounded by
    # runtime_command_timeout_s, and everything that does not need exclusion - request
    # validation and definition decoding - is done before the lock is taken.
    async with app.state.button_profile_mutation_lock:
        profile = await repository_operation(lambda: repository.get_profile(request.profile_id))
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
            await repository_operation(
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


def _validate_id(profile_id: str) -> None:
    try:
        validate_button_profile_id(profile_id)
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc
