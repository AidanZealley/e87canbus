"""Authoritative application-settings resource."""

from fastapi import APIRouter, Request

from e87canbus.api.errors import api_problem_responses
from e87canbus.api.internal import settings
from e87canbus.api.models.settings import (
    ApplicationSettingsResponse,
    UpdateApplicationSettingsRequest,
)
from e87canbus.domain.application_settings import ApplicationSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get(
    "",
    operation_id="getApplicationSettings",
    response_model=ApplicationSettingsResponse,
    responses=api_problem_responses(422, 503),
)
async def get_application_settings(request: Request) -> ApplicationSettings:
    return await settings.get_settings(request.app.state.settings_repository)


@router.put(
    "",
    operation_id="updateApplicationSettings",
    response_model=ApplicationSettingsResponse,
    responses=api_problem_responses(409, 422, 503),
)
async def update_application_settings(
    request: Request,
    body: UpdateApplicationSettingsRequest,
) -> ApplicationSettings:
    return await settings.update_settings(
        request.app,
        request.app.state.settings_repository,
        body,
    )
