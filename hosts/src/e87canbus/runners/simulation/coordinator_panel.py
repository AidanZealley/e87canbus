"""In-memory coordinator-panel edges for the browser simulator."""

from __future__ import annotations

import threading

from e87canbus.hotspot import HotspotObservation, HotspotService
from e87canbus.panel import CoordinatorStatus, PanelService
from e87canbus.runners.simulation.api.models.coordinator_panel import (
    SimulationCoordinatorPanelState,
)
from e87canbus.service import ControllerLoop, ControllerLoopLifecycle


class InMemoryHotspotBackend:
    """Model only the hotspot observations and command failures visible to the service."""

    def __init__(self) -> None:
        self.observation = HotspotObservation.DISABLED
        self.fail_next_operation = False

    def activate(self) -> None:
        self._raise_if_armed()
        self.observation = HotspotObservation.STARTING

    def deactivate(self) -> None:
        self._raise_if_armed()
        self.observation = HotspotObservation.DISABLED

    def observe(self) -> HotspotObservation:
        return self.observation

    def connect_client(self) -> None:
        if self.observation is HotspotObservation.DISABLED:
            raise ValueError("a client cannot connect while the simulated hotspot is disabled")
        self.observation = HotspotObservation.CONNECTED

    def disconnect_client(self) -> None:
        if self.observation is HotspotObservation.CONNECTED:
            self.observation = HotspotObservation.WAITING

    def arm_failure(self) -> None:
        self.fail_next_operation = True

    def _raise_if_armed(self) -> None:
        if not self.fail_next_operation:
            return
        self.fail_next_operation = False
        raise OSError("simulated hotspot operation failed")


class SimulatedCoordinatorPanel:
    """Compose the shared services and serialize browser controls around them."""

    def __init__(self, controller: ControllerLoop) -> None:
        self._controller = controller
        self._lock = threading.Lock()
        self._session_id: int | None = None
        self._preview: CoordinatorStatus | None = None
        self._reset_accessories()

    def snapshot(self) -> SimulationCoordinatorPanelState:
        with self._lock:
            self._refresh()
            return self._state()

    def press_button(self) -> SimulationCoordinatorPanelState:
        with self._lock:
            self._refresh()
            self._panel.button_pressed(self._coordinator_status)
            return self._state()

    def connect_client(self) -> SimulationCoordinatorPanelState:
        with self._lock:
            self._refresh()
            self._backend.connect_client()
            self._panel.refresh()
            return self._state()

    def disconnect_client(self) -> SimulationCoordinatorPanelState:
        with self._lock:
            self._refresh()
            self._backend.disconnect_client()
            self._panel.refresh()
            return self._state()

    def fail_next_operation(self) -> SimulationCoordinatorPanelState:
        with self._lock:
            self._refresh()
            self._backend.arm_failure()
            return self._state()

    def preview_coordinator_status(
        self,
        status: CoordinatorStatus | None,
    ) -> SimulationCoordinatorPanelState:
        with self._lock:
            self._preview = status
            self._refresh()
            return self._state()

    def _refresh(self) -> None:
        """Adopt the effective coordinator status, restarting with a new simulation session."""
        live, session_id = self._live_coordinator_status()
        if session_id is not None and session_id != self._session_id:
            self._session_id = session_id
            self._reset_accessories()
        self._coordinator_status = live if self._preview is None else self._preview
        self._panel.set_coordinator_status(self._coordinator_status)

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

    def _state(self) -> SimulationCoordinatorPanelState:
        return SimulationCoordinatorPanelState(
            coordinator_status=self._coordinator_status,
            display=self._panel.display,
            hotspot_status=self._hotspot.status(),
            failure_armed=self._backend.fail_next_operation,
            coordinator_status_preview=self._preview,
        )

    def _reset_accessories(self) -> None:
        self._backend = InMemoryHotspotBackend()
        self._hotspot = HotspotService(self._backend)
        self._panel = PanelService(self._hotspot)
        self._coordinator_status = CoordinatorStatus.STARTING
        self._preview = None
