from typing import cast

from fastapi import APIRouter, Request

from e87canbus.api.errors import api_problem_responses
from e87canbus.panel import CoordinatorStatus
from e87canbus.runners.simulation.api.models.coordinator_panel import (
    SimulationCoordinatorPanelState,
    SimulationCoordinatorStatusRequest,
)
from e87canbus.runners.simulation.coordinator_panel import SimulatedCoordinatorPanel

router = APIRouter(
    prefix="/api/dev/simulation/coordinator-panel",
    tags=["development simulation: coordinator panel"],
)


def _panel(request: Request) -> SimulatedCoordinatorPanel:
    return cast(SimulatedCoordinatorPanel, request.app.state.simulated_coordinator_panel)


@router.get("", operation_id="getSimulationCoordinatorPanel")
async def get_panel(request: Request) -> SimulationCoordinatorPanelState:
    return _panel(request).snapshot()


@router.put(
    "/coordinator-status",
    operation_id="previewSimulationCoordinatorStatus",
    responses=api_problem_responses(503),
)
async def preview_coordinator_status(
    request: Request,
    body: SimulationCoordinatorStatusRequest,
) -> SimulationCoordinatorPanelState:
    status = None if body.status is None else CoordinatorStatus(body.status)
    return _panel(request).preview_coordinator_status(status)
