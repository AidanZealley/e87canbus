"""Simulation-only CAN messages that cannot be enabled in live composition."""

from __future__ import annotations

from e87canbus.application.events import ApplicationEvent, SpeedObserved
from e87canbus.application.state import SpeedSample
from e87canbus.config import CanNetwork
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter

SIMULATION_ONLY_SPEED_ID = 0x1FFFFF00
SIMULATION_ONLY_SPEED_LENGTH = 2
MAX_SIMULATED_SPEED_KPH = 300.0


def encode_simulated_speed(speed_kph: float) -> CanFrame:
    if not 0.0 <= speed_kph <= MAX_SIMULATED_SPEED_KPH:
        raise ValueError(
            f"simulated speed must be between 0 and {MAX_SIMULATED_SPEED_KPH:g} kph"
        )
    speed_deci_kph = round(speed_kph * 10)
    return CanFrame(
        SIMULATION_ONLY_SPEED_ID,
        speed_deci_kph.to_bytes(SIMULATION_ONLY_SPEED_LENGTH, "little"),
        is_extended_id=True,
    )


class SimulationProtocolRouter(ProtocolRouter):
    """Add an unmistakably synthetic speed message to the normal project router."""

    def decode(
        self,
        routed: RoutedCanFrame,
        observed_at: float,
    ) -> ApplicationEvent | None:
        event = super().decode(routed, observed_at)
        if event is not None:
            return event
        frame = routed.frame
        if (
            routed.network is not CanNetwork.FCAN
            or frame.arbitration_id != SIMULATION_ONLY_SPEED_ID
            or not frame.is_extended_id
        ):
            return None
        if len(frame.data) != SIMULATION_ONLY_SPEED_LENGTH:
            raise ValueError(
                f"simulated speed payload must be exactly {SIMULATION_ONLY_SPEED_LENGTH} bytes"
            )
        speed_kph = int.from_bytes(frame.data, "little") / 10.0
        return SpeedObserved(SpeedSample(speed_kph, observed_at, routed.network))
