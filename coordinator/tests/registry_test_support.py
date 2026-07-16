from __future__ import annotations

import time

from e87canbus.service import ControllerService
from e87canbus.simulation.runtime import RunControlTimer


def activate_simulation_devices(service: ControllerService) -> None:
    """Drive the real simulated peers through their encoded handshake."""

    service.submit(RunControlTimer(time.monotonic())).result(timeout=1.0)
