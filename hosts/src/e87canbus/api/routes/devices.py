"""Authenticated device status and button-pad input routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from e87canbus.api.auth import DeviceRole, Principal, PrincipalKind
from e87canbus.api.errors import api_problem_responses
from e87canbus.api.internal import devices
from e87canbus.api.models.button_pad import ButtonPadPressRequest, ButtonPadStatus

router = APIRouter(prefix="/api/devices", tags=["devices"])


def button_pad_principal(request: Request) -> Principal:
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(status_code=401, detail="authentication required")
    if principal.kind is not PrincipalKind.DEVICE or principal.role is not DeviceRole.BUTTON_PAD:
        raise HTTPException(status_code=403, detail="forbidden")
    return principal


@router.post(
    "/status",
    operation_id="reportDeviceStatus",
    status_code=204,
    responses=api_problem_responses(422, 503),
)
async def report_status(
    request: Request,
    body: ButtonPadStatus,
    principal: Annotated[Principal, Depends(button_pad_principal)],
) -> Response:
    await devices.store_status(request.app, principal, body)
    return Response(status_code=204)


@router.post(
    "/button-pad/presses",
    operation_id="submitButtonPadPress",
    status_code=204,
    responses=api_problem_responses(422, 503),
)
async def submit_button_pad_press(
    request: Request,
    body: ButtonPadPressRequest,
    _principal: Annotated[Principal, Depends(button_pad_principal)],
) -> Response:
    await devices.submit_press(request.app, body)
    return Response(status_code=204)
