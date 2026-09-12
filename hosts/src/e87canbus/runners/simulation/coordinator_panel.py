"""In-memory coordinator-panel edges for the browser simulator."""

from __future__ import annotations

import threading

from e87canbus.panel import CoordinatorStatus
from e87canbus.runners.simulation.api.models.coordinator_panel import (
    SimulationCoordinatorPanelState,
)
from e87canbus.service import ControllerLoop, ControllerLoopLifecycle


class SimulatedCoordinatorPanel:
    """Expose the coordinator status projection used by the browser simulator."""

    def __init__(self, controller: ControllerLoop) -> None:
        self._controller = controller
        self._lock = threading.Lock()
        self._session_id: int | None = None
        self._preview: CoordinatorStatus | None = None

    def snapshot(self) -> SimulationCoordinatorPanelState:
        with self._lock:
            return self._state(self._refresh())

    def preview_coordinator_status(
        self,
        status: CoordinatorStatus | None,
    ) -> SimulationCoordinatorPanelState:
        with self._lock:
            self._preview = status
            return self._state(self._refresh())

    def _refresh(self) -> CoordinatorStatus:
        """Adopt the effective coordinator status, restarting with a new simulation session."""
        live, session_id = self._live_coordinator_status()
        if session_id is not None and session_id != self._session_id:
            self._session_id = session_id
            self._preview = None
        return live if self._preview is None else self._preview

    def _live_coordinator_status(self) -> tuple[CoordinatorStatus, int | None]:
        lifecycle = self._controller.lifecycle
        if lifecycle is ControllerLoopLifecycle.CREATED:
            return CoordinatorStatus.STARTING, None

        snapshot = self._controller.snapshot()
        session_id = snapshot.adapter.simulation_session_id
        if snapshot.diagnostics.health.fatal:
            return CoordinatorStatus.FAULT, session_id
        if lifecycle is ControllerLoopLifecycle.STOPPED:
            return CoordinatorStatus.OFF, session_id
        if snapshot.service.ready:
            return CoordinatorStatus.READY, session_id
        return CoordinatorStatus.STARTING, session_id

    def _state(self, status: CoordinatorStatus) -> SimulationCoordinatorPanelState:
        return SimulationCoordinatorPanelState(
            coordinator_status=status,
            coordinator_status_preview=self._preview,
        )
