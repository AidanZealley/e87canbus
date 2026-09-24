"""Authenticated device status and button-pad input routes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from e87canbus.api.auth import DeviceRole, Principal, PrincipalKind
from e87canbus.api.errors import api_problem_responses
from e87canbus.api.internal import devices
from e87canbus.api.internal.device_configuration import (
    ButtonPadConfigurationService,
    ConfigurationSubscriber,
)
from e87canbus.api.models.button_pad import (
    ButtonPadConfigurationEnvelope,
    ButtonPadPressRequest,
    ButtonPadStatus,
)

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceConfigurationStreamResponse(StreamingResponse, JSONResponse):
    media_type = "text/event-stream"

    def __init__(
        self,
        content: AsyncIterator[str],
        service: ButtonPadConfigurationService,
        subscriber: ConfigurationSubscriber,
    ) -> None:
        super().__init__(content, headers={"Cache-Control": "no-store"})
        self._service = service
        self._subscriber = subscriber

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._service.unsubscribe(self._subscriber)


def button_pad_principal(request: Request) -> Principal:
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(status_code=401, detail="authentication required")
    if principal.kind is not PrincipalKind.DEVICE or principal.role is not DeviceRole.BUTTON_PAD:
        raise HTTPException(status_code=403, detail="forbidden")
    return principal


@router.get(
    "/configuration",
    operation_id="streamDeviceConfiguration",
    status_code=200,
    response_model=ButtonPadConfigurationEnvelope,
    response_class=DeviceConfigurationStreamResponse,
)
async def stream_configuration(
    request: Request,
    principal: Annotated[Principal, Depends(button_pad_principal)],
) -> DeviceConfigurationStreamResponse:
    task = request.state.configuration_request_task
    if task is None or principal.device_id is None:
        raise RuntimeError("device configuration route requires an authenticated request task")
    service: ButtonPadConfigurationService = request.app.state.device_configuration
    subscriber = await service.subscribe(principal.device_id, task)
    return DeviceConfigurationStreamResponse(service.events(subscriber), service, subscriber)


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
