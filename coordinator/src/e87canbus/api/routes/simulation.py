"""Simulation-session and button-control routes."""

from typing import Any

from fastapi import APIRouter, Request

from e87canbus.api.internal.simulation import run_command, submit
from e87canbus.api.models.simulation import StepRequest
from e87canbus.simulation.engine import (
    PressButton,
    ReleaseButton,
    ResetSimulation,
    StepButton,
    snapshot_to_dict,
)

router = APIRouter(prefix="/api", tags=["simulation"])


@router.get("/snapshot")
async def snapshot(request: Request) -> dict[str, Any]:
    return snapshot_to_dict(request.app.state.latest_snapshot, include_trace=True)


@router.post("/reset")
async def reset(request: Request) -> dict[str, Any]:
    result = await submit(request.app, ResetSimulation())
    return snapshot_to_dict(result.snapshot, include_trace=True)


@router.post("/buttons/{button_index}/press")
async def press_button(request: Request, button_index: int) -> dict[str, Any]:
    return await run_command(request.app, PressButton(button_index))


@router.post("/buttons/{button_index}/release")
async def release_button(request: Request, button_index: int) -> dict[str, Any]:
    return await run_command(request.app, ReleaseButton(button_index))


@router.post("/step")
async def step(request: Request, body: StepRequest) -> dict[str, Any]:
    return await run_command(request.app, StepButton(body.button_index))
