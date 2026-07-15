"""Authoritative application-settings resource."""

from typing import Any

from fastapi import APIRouter, Request

from e87canbus.api.internal import settings
from e87canbus.api.models.settings import UpdateApplicationSettingsRequest

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_application_settings(request: Request) -> dict[str, Any]:
    return await settings.get_settings(request.app.state.settings_repository)


@router.put("")
async def update_application_settings(
    request: Request,
    body: UpdateApplicationSettingsRequest,
) -> dict[str, Any]:
    return await settings.update_settings(
        request.app,
        request.app.state.settings_repository,
        body,
    )
