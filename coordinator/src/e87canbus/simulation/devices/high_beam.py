"""The simulator-only high-beam actuator."""

from __future__ import annotations

from dataclasses import dataclass

from e87canbus.adapters.output import SafeCanTransmitter
from e87canbus.domain.events import SetHighBeam


@dataclass(frozen=True)
class SimulatedHighBeamActuator:
    """Simulator-only high-beam capability using the private virtual-car frame."""

    transmitter: SafeCanTransmitter

    def set_high_beam(self, command: SetHighBeam) -> None:
        from e87canbus.simulation.protocol import encode_simulated_high_beam_command

        self.transmitter.send(encode_simulated_high_beam_command(command.enabled))
