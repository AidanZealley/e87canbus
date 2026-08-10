from __future__ import annotations

import time

from e87canbus.runners.simulation.runtime import RunControlTimer
from e87canbus.service import ControllerLoop


def activate_simulation_devices(service: ControllerLoop) -> None:
    """Drive the real simulated peers through their encoded handshake."""

    service.submit(RunControlTimer(time.monotonic())).result(timeout=1.0)
