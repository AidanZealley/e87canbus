"""The virtual Servotronic peer with an in-process actuator model."""

from __future__ import annotations

import time
from collections.abc import Callable

from e87canbus.adapters.can_io import CanEndpoint
from e87canbus.config import CustomCanIds
from e87canbus.domain.device import DeviceRole
from e87canbus.domain.events import SetSteeringAssistance, SteeringCommandReason
from e87canbus.simulation.devices.peer import SimulatedRegistryPeer


class SimulatedServotronicPeer(SimulatedRegistryPeer):
    """Virtual Servotronic peer with an in-process dimensionless actuator model."""

    def __init__(
        self,
        watchdog_timeout_s: float,
        clock: Callable[[], float] = time.monotonic,
        *,
        bus: CanEndpoint | None = None,
        ids: CustomCanIds | None = None,
    ) -> None:
        super().__init__(
            role=DeviceRole.SERVOTRONIC_CONTROLLER,
            bus=bus,
            ids=ids,
            clock=clock,
        )
        self.watchdog_timeout_s = watchdog_timeout_s
        self.last_command: SetSteeringAssistance | None = None
        self.last_command_at: float | None = None

    def set_assistance(self, command: SetSteeringAssistance) -> None:
        self.last_command = command
        self.last_command_at = self.clock()

    @property
    def watchdog_timed_out(self) -> bool:
        return self.last_command_at is None or (
            self.clock() - self.last_command_at > self.watchdog_timeout_s
        )

    @property
    def effective_assistance(self) -> float:
        if self.watchdog_timed_out or self.last_command is None:
            return 0.0
        return self.last_command.assistance

    @property
    def last_command_reason(self) -> SteeringCommandReason | None:
        return None if self.last_command is None else self.last_command.reason
