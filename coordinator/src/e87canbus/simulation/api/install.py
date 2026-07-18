from fastapi import FastAPI

from e87canbus.deployment import SimulationApiScope
from e87canbus.simulation.api.routes import devices, session, vehicle


def install_simulation_api(
    app: FastAPI,
    scope: SimulationApiScope,
) -> None:
    if scope in {SimulationApiScope.VEHICLE, SimulationApiScope.FULL}:
        app.include_router(vehicle.router)
    if scope is SimulationApiScope.FULL:
        app.include_router(devices.router)
        app.include_router(session.router)
