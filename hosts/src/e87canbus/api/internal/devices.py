"""Button-pad status persistence and controller input submission."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI

from e87canbus.adapters.sqlite_device_state import DeviceStateStorageError
from e87canbus.api.auth import DeviceRole, Principal
from e87canbus.api.errors import ApiProblem
from e87canbus.api.internal.commands import submit_runtime_work
from e87canbus.api.models.button_pad import ButtonPadPressRequest, ButtonPadStatus
from e87canbus.domain.events import ButtonPressed


async def store_status(app: FastAPI, principal: Principal, status: ButtonPadStatus) -> None:
    assert principal.device_id is not None
    try:
        await asyncio.to_thread(
            app.state.device_state_repository.upsert_status,
            principal.device_id,
            DeviceRole.BUTTON_PAD,
            status,
        )
    except DeviceStateStorageError as exc:
        raise ApiProblem(503, "device_storage_error", "could not store device status") from exc


async def submit_press(app: FastAPI, body: ButtonPadPressRequest) -> None:
    await submit_runtime_work(
        app, ButtonPressed(body.button_index, observed_at=app.state.monotonic_clock())
    )
