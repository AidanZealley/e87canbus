"""Physical coordinator-panel composition and lifecycle."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from e87canbus.adapters.coordinator_panel import UartPanelAdapter, open_uart_panel
from e87canbus.panel import CoordinatorStatus
from e87canbus.service import ControllerLoop, ControllerLoopLifecycle

LOGGER = logging.getLogger(__name__)


class PhysicalCoordinatorPanel:
    """Publish coordinator status to the physical panel."""

    def __init__(
        self,
        controller: ControllerLoop,
        *,
        uart_factory: Callable[[], UartPanelAdapter] = open_uart_panel,
    ) -> None:
        self._controller = controller
        self._uart_factory = uart_factory
        self._stop = threading.Event()
        # A fault leaves the panel dark so the firmware times out into red. Only a
        # requested stop sends `off`, which is the graceful-shutdown appearance.
        self._faulted = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run,
            name="coordinator-panel",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        uart: UartPanelAdapter | None = None
        try:
            uart = self._uart_factory()
            while not self._stop.is_set():
                uart.display(self._coordinator_status())
                self._stop.wait(1.0)
        except Exception:
            LOGGER.exception("coordinator panel UART stopped after an I/O failure")
            self._fault()
        finally:
            if uart is not None:
                try:
                    if not self._faulted:
                        uart.display(CoordinatorStatus.OFF)
                    uart.close()
                except Exception:
                    LOGGER.exception("failed to close the coordinator panel UART")

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
