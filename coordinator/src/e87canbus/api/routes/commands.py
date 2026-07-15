"""Typed semantic controller commands."""

from fastapi import APIRouter, Request

from e87canbus.api.internal import operational_commands
from e87canbus.api.models.commands import (
    ActivateSteeringCurveRequest,
    ActivateSteeringProfileRequest,
    CommandAcknowledgement,
    SetMaximumAssistanceRequest,
    SetSteeringModeRequest,
)

router = APIRouter(prefix="/api/commands", tags=["commands"])


@router.put("/maximum-assistance")
async def set_maximum_assistance(
    request: Request,
    body: SetMaximumAssistanceRequest,
) -> CommandAcknowledgement:
    return await operational_commands.set_maximum_assistance(request.app, body)


@router.put("/steering-mode")
async def set_steering_mode(
    request: Request,
    body: SetSteeringModeRequest,
) -> CommandAcknowledgement:
    return await operational_commands.set_steering_mode(request.app, body)


@router.post("/activate-steering-profile")
async def activate_steering_profile(
    request: Request,
    body: ActivateSteeringProfileRequest,
) -> CommandAcknowledgement:
    return await operational_commands.activate_steering_profile(
        request.app,
        request.app.state.profile_repository,
        body,
    )


@router.put("/steering-curve")
async def activate_steering_curve(
    request: Request,
    body: ActivateSteeringCurveRequest,
) -> CommandAcknowledgement:
    return await operational_commands.activate_steering_curve(request.app, body)
