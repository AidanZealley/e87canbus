"""Semantic operational-command use cases."""

from __future__ import annotations

from fastapi import FastAPI

from e87canbus.api.errors import ApiProblem
from e87canbus.api.internal.commands import submit_command
from e87canbus.api.internal.steering import (
    definition_from_request,
    repository_operation,
    validate_profile_id,
)
from e87canbus.api.models.commands import (
    ActivateSteeringCurveRequest,
    ActivateSteeringProfileRequest,
    AdjustManualAssistanceRequest,
    CommandAcknowledgement,
    SetManualAssistanceLevelRequest,
    SetMaximumAssistanceRequest,
    SetSteeringModeRequest,
)
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
)
from e87canbus.domain.profile_repository import SteeringProfileRepository
from e87canbus.domain.state import SteeringMode
from e87canbus.domain.steering import SteeringCurveDefinition
from e87canbus.kernel import (
    ActivateSteeringCurve,
    ExecuteOperatorIntent,
)


async def set_maximum_assistance(
    app: FastAPI,
    request: SetMaximumAssistanceRequest,
) -> CommandAcknowledgement:
    return await submit_command(app, ExecuteOperatorIntent(SetMaximumAssistance(request.enabled)))


async def set_steering_mode(
    app: FastAPI,
    request: SetSteeringModeRequest,
) -> CommandAcknowledgement:
    return await submit_command(
        app, ExecuteOperatorIntent(SelectSteeringMode(SteeringMode(request.mode)))
    )


async def adjust_manual_assistance(
    app: FastAPI,
    request: AdjustManualAssistanceRequest,
) -> CommandAcknowledgement:
    return await submit_command(app, ExecuteOperatorIntent(AdjustManualAssistance(request.delta)))


async def set_manual_assistance_level(
    app: FastAPI,
    request: SetManualAssistanceLevelRequest,
) -> CommandAcknowledgement:
    manual_level = request.level
    manual_level_count = app.state.controller_service.config.steering.manual_level_count
    if manual_level >= manual_level_count:
        raise ApiProblem(
            422,
            "validation_error",
            f"manual assistance level must be between 0 and {manual_level_count - 1}",
        )
    return await submit_command(
        app,
        ExecuteOperatorIntent(SetManualAssistanceLevel(manual_level)),
    )


async def activate_steering_profile(
    app: FastAPI,
    repository: SteeringProfileRepository,
    request: ActivateSteeringProfileRequest,
) -> CommandAcknowledgement:
    validate_profile_id(request.profile_id)
    profile = await repository_operation(lambda: repository.get_profile(request.profile_id))
    if profile is None:
        raise ApiProblem(
            404,
            "profile_not_found",
            f"steering profile not found: {request.profile_id}",
        )
    if profile.revision != request.expected_revision:
        raise ApiProblem(
            409,
            "profile_revision_conflict",
            f"steering profile {profile.profile_id} is at revision {profile.revision}, "
            f"not {request.expected_revision}",
            current_revision=profile.revision,
        )
    return await _activate(
        app,
        definition=profile.definition,
        profile_id=profile.profile_id,
        profile_revision=profile.revision,
    )


async def activate_steering_curve(
    app: FastAPI,
    request: ActivateSteeringCurveRequest,
) -> CommandAcknowledgement:
    return await _activate(
        app,
        definition=definition_from_request(request.definition),
        profile_id=None,
        profile_revision=None,
    )


async def _activate(
    app: FastAPI,
    *,
    definition: SteeringCurveDefinition,
    profile_id: str | None,
    profile_revision: int | None,
) -> CommandAcknowledgement:
    return await submit_command(
        app,
        ActivateSteeringCurve(
            definition,
            profile_id,
            profile_revision,
            requested_at=app.state.monotonic_clock(),
        ),
    )
