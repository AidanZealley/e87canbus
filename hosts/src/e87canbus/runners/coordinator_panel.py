"""Physical coordinator-panel composition and lifecycle."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable

from e87canbus.adapters.coordinator_panel import UartPanelAdapter, open_uart_panel
from e87canbus.adapters.networkmanager_hotspot import NetworkManagerHotspotBackend
from e87canbus.hotspot import HotspotBackend, HotspotService
from e87canbus.panel import CoordinatorStatus, PanelDisplay, PanelService
from e87canbus.service import ControllerLoop, ControllerLoopLifecycle

LOGGER = logging.getLogger(__name__)


class PhysicalCoordinatorPanel:
    """Run bounded UART timing independently of slower NetworkManager work."""

    def __init__(
        self,
        controller: ControllerLoop,
        *,
        uart_factory: Callable[[], UartPanelAdapter] = open_uart_panel,
        hotspot_backend: HotspotBackend | None = None,
    ) -> None:
        self._controller = controller
        self._uart_factory = uart_factory
        self._hotspot_backend = hotspot_backend or NetworkManagerHotspotBackend()
        self._stop = threading.Event()
        # A fault leaves the panel dark so the firmware times out into red. Only a
        # requested stop sends `off`, which is the graceful-shutdown appearance.
        self._faulted = False
        self._buttons: queue.SimpleQueue[CoordinatorStatus] = queue.SimpleQueue()
        # Published by the state thread, read by the UART thread.
        self._display = PanelDisplay.STARTING
        self._uart_thread: threading.Thread | None = None
        self._state_thread: threading.Thread | None = None

    def start(self) -> None:
        # NetworkManager can consume most of its command timeout. A single direct loop
        # therefore cannot also guarantee the panel's one-second UART heartbeat.
        self._uart_thread = threading.Thread(
            target=self._run_uart,
            name="coordinator-panel",
            daemon=True,
        )
        self._state_thread = threading.Thread(
            target=self._run_state,
            name="coordinator-panel-state",
            daemon=True,
        )
        self._uart_thread.start()
        self._state_thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._uart_thread is not None:
            self._uart_thread.join(timeout=1.0)
        if self._state_thread is not None:
            self._state_thread.join(timeout=12.0)

    def _run_uart(self) -> None:
        uart: UartPanelAdapter | None = None
        try:
            uart = self._uart_factory()
            next_heartbeat = time.monotonic()
            while not self._stop.is_set():
                for _ in range(uart.read_button_presses()):
                    self._buttons.put(self._coordinator_status())
                now = time.monotonic()
                if now >= next_heartbeat:
                    uart.display(self._display)
                    next_heartbeat += 1.0
        except Exception:
            LOGGER.exception("coordinator panel UART stopped after an I/O failure")
            self._fault()
        finally:
            if uart is not None:
                try:
                    if not self._faulted:
                        uart.display(PanelDisplay.OFF)
                    uart.close()
                except Exception:
                    LOGGER.exception("failed to close the coordinator panel UART")

    def _run_state(self) -> None:
        try:
            panel = PanelService(HotspotService(self._hotspot_backend))
            panel.set_coordinator_status(self._coordinator_status())
            self._display = panel.display
            while not self._stop.is_set():
                try:
                    button_status = self._buttons.get(timeout=1.0)
                except queue.Empty:
                    panel.set_coordinator_status(self._coordinator_status())
                else:
                    panel.button_pressed(button_status)
                self._display = panel.display
        except Exception:
            LOGGER.exception("coordinator panel state worker stopped after an I/O failure")
            self._fault()

    def _fault(self) -> None:
        self._faulted = True
        self._stop.set()

    def _coordinator_status(self) -> CoordinatorStatus:
        lifecycle = self._controller.lifecycle
        if lifecycle is ControllerLoopLifecycle.CREATED:
            return CoordinatorStatus.STARTING
        snapshot = self._controller.snapshot()
        if snapshot.diagnostics.health.fatal:
            return CoordinatorStatus.FAULT
        if lifecycle is ControllerLoopLifecycle.STOPPED:
            return CoordinatorStatus.OFF
        if snapshot.service.ready:
            return CoordinatorStatus.READY
        return CoordinatorStatus.STARTING
