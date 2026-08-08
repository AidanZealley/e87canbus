from fastapi import FastAPI

from e87canbus.deployment import SimulationApiScope
from e87canbus.runners.simulation.api.routes import coordinator_panel, devices, session, vehicle
from e87canbus.runners.simulation.coordinator_panel import SimulatedCoordinatorPanel
from e87canbus.service import ControllerLoop


def install_simulation_api(
    app: FastAPI,
    scope: SimulationApiScope,
    controller: ControllerLoop,
) -> None:
    if scope in {SimulationApiScope.VEHICLE, SimulationApiScope.FULL}:
        app.include_router(vehicle.router)
    if scope is SimulationApiScope.FULL:
        app.state.simulated_coordinator_panel = SimulatedCoordinatorPanel(controller)
        app.include_router(coordinator_panel.router)
        app.include_router(devices.router)
        app.include_router(session.router)
