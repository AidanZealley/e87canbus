from collections.abc import Callable
from typing import cast

from fastapi import APIRouter, Request

from e87canbus.api.errors import ApiProblem, api_problem_responses
from e87canbus.panel import CoordinatorStatus
from e87canbus.runners.simulation.api.models.coordinator_panel import (
    SimulationCoordinatorPanelState,
    SimulationCoordinatorStatusRequest,
)
from e87canbus.runners.simulation.coordinator_panel import (
    SimulatedCoordinatorPanel,
    SimulatedPanelState,
)

router = APIRouter(
    prefix="/api/dev/simulation/coordinator-panel",
    tags=["development simulation: coordinator panel"],
)


def _panel(request: Request) -> SimulatedCoordinatorPanel:
    return cast(SimulatedCoordinatorPanel, request.app.state.simulated_coordinator_panel)


def _state(
    operation: Callable[[], SimulatedPanelState],
) -> SimulationCoordinatorPanelState:
    try:
        (
            coordinator_status,
            display,
            hotspot_status,
            failure_armed,
            coordinator_status_preview,
        ) = operation()
    except ValueError as exc:
        raise ApiProblem(409, "feature_unavailable", str(exc)) from exc
    return SimulationCoordinatorPanelState(
        coordinator_status=coordinator_status,
        display=display,
        hotspot_status=hotspot_status,
        failure_armed=failure_armed,
        coordinator_status_preview=coordinator_status_preview,
    )


@router.get("", operation_id="getSimulationCoordinatorPanel")
async def get_panel(request: Request) -> SimulationCoordinatorPanelState:
    return _state(_panel(request).snapshot)


@router.post(
    "/button",
    operation_id="pressSimulationCoordinatorPanelButton",
    responses=api_problem_responses(409, 503),
)
async def press_button(request: Request) -> SimulationCoordinatorPanelState:
    return _state(_panel(request).press_button)


@router.post(
    "/client/connect",
    operation_id="connectSimulationHotspotClient",
    responses=api_problem_responses(409, 503),
)
async def connect_client(request: Request) -> SimulationCoordinatorPanelState:
    return _state(_panel(request).connect_client)


@router.post(
    "/client/disconnect",
    operation_id="disconnectSimulationHotspotClient",
    responses=api_problem_responses(409, 503),
)
async def disconnect_client(request: Request) -> SimulationCoordinatorPanelState:
    return _state(_panel(request).disconnect_client)


@router.post(
    "/hotspot/fail-next-operation",
    operation_id="failNextSimulationHotspotOperation",
    responses=api_problem_responses(503),
)
async def fail_next_operation(request: Request) -> SimulationCoordinatorPanelState:
    return _state(_panel(request).fail_next_operation)


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
    return _state(lambda: _panel(request).preview_coordinator_status(status))
