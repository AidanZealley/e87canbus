from fastapi import APIRouter, Request

from e87canbus.api.errors import api_problem_responses
from e87canbus.runners.simulation.api.internal.local_controls import (
    run_local_controls_command,
)
from e87canbus.runners.simulation.api.models.common import SimulationCommandAcknowledgement
from e87canbus.runners.simulation.api.models.local_controls import (
    SimulatedConnectionRequest,
    SimulatedFailureRequest,
)
from e87canbus.runners.simulation.commands import (
    SetSimulatedHotspotClient,
    SetSimulatedHotspotFailure,
    SetSimulatedPanelLink,
    TapCoordinatorPanelButton,
)

router = APIRouter(
    prefix="/api/dev/simulation/coordinator-panel",
    tags=["development simulation: coordinator panel"],
)


@router.post(
    "/button/tap",
    operation_id="tapCoordinatorPanelButton",
    responses=api_problem_responses(409, 503),
)
async def tap_button(request: Request) -> SimulationCommandAcknowledgement:
    return await run_local_controls_command(request.app, TapCoordinatorPanelButton())


@router.put(
    "/client",
    operation_id="setSimulatedHotspotClient",
    responses=api_problem_responses(409, 422, 503),
)
async def set_client(
    request: Request, body: SimulatedConnectionRequest
) -> SimulationCommandAcknowledgement:
    return await run_local_controls_command(
        request.app, SetSimulatedHotspotClient(body.connected)
    )


@router.put(
    "/link",
    operation_id="setSimulatedPanelLink",
    responses=api_problem_responses(409, 422, 503),
)
async def set_link(
    request: Request, body: SimulatedConnectionRequest
) -> SimulationCommandAcknowledgement:
    return await run_local_controls_command(
        request.app, SetSimulatedPanelLink(body.connected)
    )


@router.put(
    "/hotspot-failure",
    operation_id="setSimulatedHotspotFailure",
    responses=api_problem_responses(409, 422, 503),
)
async def set_hotspot_failure(
    request: Request, body: SimulatedFailureRequest
) -> SimulationCommandAcknowledgement:
    return await run_local_controls_command(
        request.app, SetSimulatedHotspotFailure(body.enabled)
    )
