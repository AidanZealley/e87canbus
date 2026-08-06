"""HTTP command seam for simulation-only coordinator panel causes."""

from fastapi import FastAPI

from e87canbus.api.errors import ApiProblem
from e87canbus.local_controls.model import PanelLink
from e87canbus.runners.simulation.api.models.common import SimulationCommandAcknowledgement
from e87canbus.runners.simulation.commands import (
    LocalControlsSimulationCommand,
    SetSimulatedHotspotClient,
    SetSimulatedHotspotFailure,
    SetSimulatedPanelLink,
    TapCoordinatorPanelButton,
)


async def run_local_controls_command(
    app: FastAPI,
    command: LocalControlsSimulationCommand,
) -> SimulationCommandAcknowledgement:
    simulation = app.state.simulated_local_controls
    accepted = True
    match command:
        case TapCoordinatorPanelButton():
            accepted = simulation.panel.tap_button()
        case SetSimulatedHotspotClient(connected):
            accepted = simulation.hotspot.set_client_connected(connected)
        case SetSimulatedPanelLink(connected):
            accepted = simulation.panel.set_link(
                PanelLink.CONNECTED if connected else PanelLink.DISCONNECTED
            )
        case SetSimulatedHotspotFailure(enabled):
            accepted = simulation.hotspot.set_failure(enabled)

    if not accepted:
        raise ApiProblem(409, "feature_unavailable", "simulated cause is not currently valid")
    return SimulationCommandAcknowledgement(boot_id=app.state.controller_loop.boot_id)
