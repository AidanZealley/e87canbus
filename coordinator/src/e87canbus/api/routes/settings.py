"""Authoritative application-settings resource."""

from fastapi import APIRouter, Request

from e87canbus.api.internal import settings
from e87canbus.api.models.settings import UpdateApplicationSettingsRequest
from e87canbus.features.application_settings import ApplicationSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_application_settings(request: Request) -> ApplicationSettings:
    return await settings.get_settings(request.app.state.settings_repository)


@router.put("")
async def update_application_settings(
    request: Request,
    body: UpdateApplicationSettingsRequest,
) -> ApplicationSettings:
    return await settings.update_settings(
        request.app,
        request.app.state.settings_repository,
        body,
    )
