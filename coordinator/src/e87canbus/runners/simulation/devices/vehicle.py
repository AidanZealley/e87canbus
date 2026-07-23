"""The external simulated vehicle node with explicitly synthetic messages."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from e87canbus.adapters.can_io import CanEndpoint
from e87canbus.config import CanNetwork
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
from e87canbus.runners.simulation.commands import SetVehicleSignal, SilenceVehicleSignal
from e87canbus.runners.simulation.protocol import (
    SIMULATION_ONLY_HIGH_BEAM_COMMAND_ID,
    decode_simulated_high_beam_command,
)
from e87canbus.runners.simulation.vehicle_source import SyntheticVehicleSource

LOGGER = logging.getLogger(__name__)


@dataclass
class SimulatedVehicleNode:
    """External simulation node with explicitly synthetic vehicle messages."""

    buses: dict[CanNetwork, CanEndpoint]
    signals: SyntheticVehicleSource = field(default_factory=SyntheticVehicleSource)
    high_beam_enabled: bool = False

    def execute(self, command: SetVehicleSignal | SilenceVehicleSignal) -> None:
        self._send(self.signals.execute(command))

    def emit(self) -> None:
        self._send(self.signals.emit())

    def _send(self, frames: tuple[RoutedCanFrame, ...]) -> None:
        for routed in frames:
            self.buses[routed.network].send(routed.frame)

    def drain_pending(self) -> int:
        drained = 0
        for network in CanNetwork:
            bus = self.buses.get(network)
            if bus is None:
                continue
            while (frame := bus.receive(timeout_s=0)) is not None:
                drained += 1
                self._consume_frame(network, frame)
        return drained

    def _consume_frame(self, network: CanNetwork, frame: CanFrame) -> None:
        if (
            network is not CanNetwork.KCAN
            or not frame.is_extended_id
            or frame.arbitration_id != SIMULATION_ONLY_HIGH_BEAM_COMMAND_ID
        ):
            return
        try:
            self.high_beam_enabled = decode_simulated_high_beam_command(frame)
        except ValueError as exc:
            LOGGER.warning(
                "simulated vehicle ignored malformed high-beam command: data=%s error=%s",
                frame.data.hex(),
                exc,
            )
