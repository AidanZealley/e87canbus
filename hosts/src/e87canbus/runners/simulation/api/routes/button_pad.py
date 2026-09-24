"""Development button tap through the independent simulated pad."""

from fastapi import APIRouter, Request

from e87canbus.api.errors import api_problem_responses
from e87canbus.api.models.button_pad import ButtonPadPressRequest
from e87canbus.runners.simulation.api.models.common import SimulationCommandAcknowledgement
from e87canbus.runners.simulation.devices.button_pad import SimulatedButtonPad

router = APIRouter(
    prefix="/api/dev/simulation/button-pad",
    tags=["development simulation: button pad"],
)


@router.post(
    "/tap",
    operation_id="tapSimulatedButtonPad",
    responses=api_problem_responses(422, 503),
)
async def tap_button_pad(
    request: Request, body: ButtonPadPressRequest
) -> SimulationCommandAcknowledgement:
    client: SimulatedButtonPad = request.app.state.simulated_button_pad
    await client.press(body.button_index)
    return SimulationCommandAcknowledgement(boot_id=request.app.state.controller_loop.boot_id)
