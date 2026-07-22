"""Typed semantic controller commands."""

from fastapi import APIRouter, Request

from e87canbus.api.errors import api_problem_responses
from e87canbus.api.internal import operational_commands
from e87canbus.api.models.commands import (
    ActivateSteeringCurveRequest,
    ActivateSteeringProfileRequest,
    AdjustManualAssistanceRequest,
    CommandAcknowledgement,
    SetManualAssistanceLevelRequest,
    SetMaximumAssistanceRequest,
    SetSteeringModeRequest,
)

router = APIRouter(prefix="/api/commands", tags=["commands"])


@router.put(
    "/maximum-assistance",
    operation_id="setMaximumAssistance",
    responses=api_problem_responses(409, 422, 503),
)
async def set_maximum_assistance(
    request: Request,
    body: SetMaximumAssistanceRequest,
) -> CommandAcknowledgement:
    return await operational_commands.set_maximum_assistance(request.app, body)


@router.put(
    "/steering-mode",
    operation_id="setSteeringMode",
    responses=api_problem_responses(409, 422, 503),
)
async def set_steering_mode(
    request: Request,
    body: SetSteeringModeRequest,
) -> CommandAcknowledgement:
    return await operational_commands.set_steering_mode(request.app, body)


@router.post(
    "/manual-assistance-adjustment",
    operation_id="adjustManualAssistance",
    responses=api_problem_responses(409, 422, 503),
)
async def adjust_manual_assistance(
    request: Request,
    body: AdjustManualAssistanceRequest,
) -> CommandAcknowledgement:
    return await operational_commands.adjust_manual_assistance(request.app, body)


@router.put(
    "/manual-assistance-level",
    operation_id="setManualAssistanceLevel",
    responses=api_problem_responses(409, 422, 503),
)
async def set_manual_assistance_level(
    request: Request,
    body: SetManualAssistanceLevelRequest,
) -> CommandAcknowledgement:
    return await operational_commands.set_manual_assistance_level(request.app, body)


@router.post(
    "/activate-steering-profile",
    operation_id="activateSteeringProfile",
    responses=api_problem_responses(404, 409, 422, 503),
)
async def activate_steering_profile(
    request: Request,
    body: ActivateSteeringProfileRequest,
) -> CommandAcknowledgement:
    return await operational_commands.activate_steering_profile(
        request.app,
        request.app.state.profile_repository,
        body,
    )


@router.put(
    "/steering-curve",
    operation_id="activateSteeringCurve",
    responses=api_problem_responses(409, 422, 503),
)
async def activate_steering_curve(
    request: Request,
    body: ActivateSteeringCurveRequest,
) -> CommandAcknowledgement:
    return await operational_commands.activate_steering_curve(request.app, body)
