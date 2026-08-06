"""Development simulation actions backed by the unified controller service."""

import asyncio

from fastapi import FastAPI

from e87canbus.api.errors import ApiProblem
from e87canbus.api.internal.commands import submit_runtime_work
from e87canbus.local_controls.model import (
    CoordinatorCondition,
    CoordinatorConditionChanged,
    HotspotLifecycle,
    HotspotObserved,
    LocalControlsEvent,
    PanelLink,
    PanelLinkChanged,
)
from e87canbus.local_controls.service import LocalControlsService
from e87canbus.runners.simulation.api.models.common import SimulationCommandAcknowledgement
from e87canbus.runners.simulation.commands import (
    ResetSimulation,
    SimulationCommand,
    TriggerCoordinatorFailure,
)


async def run_command(
    app: FastAPI,
    command: SimulationCommand,
) -> SimulationCommandAcknowledgement:
    if isinstance(command, ResetSimulation):
        await _reset_simulation(app, command)
    elif isinstance(command, TriggerCoordinatorFailure):
        await _trigger_coordinator_failure(app, command)
    else:
        await submit_runtime_work(app, command)
    return SimulationCommandAcknowledgement(boot_id=app.state.controller_loop.boot_id)


async def _reset_simulation(app: FastAPI, command: ResetSimulation) -> None:
    simulation = app.state.simulated_local_controls
    if simulation is not None:
        await _submit_local(
            simulation.service,
            CoordinatorConditionChanged(CoordinatorCondition.SHUTTING_DOWN),
        )
    try:
        await submit_runtime_work(app, command)
    except BaseException:
        if simulation is not None:
            condition = simulation.coordinator_condition.resynchronize()
            await _submit_local(
                simulation.service,
                CoordinatorConditionChanged(condition),
            )
        raise
    if simulation is None:
        return
    simulation.panel.reset()
    simulation.hotspot.reset()
    await _submit_local(simulation.service, PanelLinkChanged(PanelLink.CONNECTED))
    await _submit_local(simulation.service, HotspotObserved(HotspotLifecycle.DISABLED))
    simulation.coordinator_condition.begin_simulated_restart()
    await _submit_local(
        simulation.service,
        CoordinatorConditionChanged(CoordinatorCondition.STARTING),
    )


async def _trigger_coordinator_failure(
    app: FastAPI,
    command: TriggerCoordinatorFailure,
) -> None:
    try:
        await submit_runtime_work(app, command)
    except ApiProblem as exc:
        # Entering fatal health makes the generic command seam reject its own future.
        # For this explicit simulator cause, fatal health is the successful outcome.
        if exc.code != "controller_failed" or not app.state.controller_loop.fatal:
            raise


async def _submit_local(
    service: LocalControlsService,
    event: LocalControlsEvent,
) -> None:
    future = service.submit(event)
    await asyncio.wrap_future(future)
