"""Simulation-only CAN messages that cannot be enabled in live composition."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from e87canbus.application.events import (
    ApplicationEvent,
    CoolantTemperatureObserved,
    EngineRpmObserved,
    OilTemperatureObserved,
    SpeedObserved,
)
from e87canbus.application.state import (
    CoolantTemperatureSample,
    EngineRpmSample,
    OilTemperatureSample,
    SpeedSample,
)
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.device_registry import RegistryHeartbeatObserved, RegistryHelloObserved
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.simulation.signals import VehicleSignal

SIMULATION_ONLY_SPEED_ID = 0x1FFFFF00
SIMULATION_ONLY_ENGINE_RPM_ID = 0x1FFFFF01
SIMULATION_ONLY_OIL_TEMPERATURE_ID = 0x1FFFFF02
SIMULATION_ONLY_COOLANT_TEMPERATURE_ID = 0x1FFFFF03
SIMULATION_ONLY_HIGH_BEAM_COMMAND_ID = 0x1FFFFF04
SIMULATION_ONLY_SPEED_LENGTH = 2
SIMULATION_ONLY_ENGINE_RPM_LENGTH = 2
SIMULATION_ONLY_TEMPERATURE_LENGTH = 2
SIMULATION_ONLY_HIGH_BEAM_COMMAND_LENGTH = 1
MAX_SIMULATED_SPEED_KPH = 300.0
MAX_SIMULATED_ENGINE_RPM = 12_000
MIN_SIMULATED_TEMPERATURE_C = -40.0
MAX_SIMULATED_TEMPERATURE_C = 250.0


def encode_simulated_high_beam_command(enabled: bool) -> CanFrame:
    """Encode the simulator-private Pi-to-vehicle high-beam command.

    This extended-ID frame deliberately has no BMW mapping and is consumed only
    by :class:`SimulatedVehicleNode`.  It must never be added to the live router.
    """

    if not isinstance(enabled, bool):
        raise ValueError("simulated high-beam command must be a boolean")
    return CanFrame(
        SIMULATION_ONLY_HIGH_BEAM_COMMAND_ID,
        bytes((int(enabled),)),
        is_extended_id=True,
    )


def decode_simulated_high_beam_command(frame: CanFrame) -> bool:
    """Decode the payload of a recognized simulator-private high-beam command."""

    if len(frame.data) != SIMULATION_ONLY_HIGH_BEAM_COMMAND_LENGTH:
        raise ValueError(
            "simulated high-beam command payload must be exactly "
            f"{SIMULATION_ONLY_HIGH_BEAM_COMMAND_LENGTH} byte"
        )
    if frame.data not in (b"\x00", b"\x01"):
        raise ValueError("simulated high-beam command payload must be 0 or 1")
    return bool(frame.data[0])


def encode_simulated_speed(speed_kph: float) -> CanFrame:
    if not 0.0 <= speed_kph <= MAX_SIMULATED_SPEED_KPH:
        raise ValueError(f"simulated speed must be between 0 and {MAX_SIMULATED_SPEED_KPH:g} kph")
    speed_deci_kph = round(speed_kph * 10)
    return CanFrame(
        SIMULATION_ONLY_SPEED_ID,
        speed_deci_kph.to_bytes(SIMULATION_ONLY_SPEED_LENGTH, "little"),
        is_extended_id=True,
    )


def encode_simulated_engine_rpm(rpm: int) -> CanFrame:
    if isinstance(rpm, bool) or not isinstance(rpm, int):
        raise ValueError("simulated engine RPM must be an integer")
    if not 0 <= rpm <= MAX_SIMULATED_ENGINE_RPM:
        raise ValueError(f"simulated engine RPM must be between 0 and {MAX_SIMULATED_ENGINE_RPM}")
    return CanFrame(
        SIMULATION_ONLY_ENGINE_RPM_ID,
        rpm.to_bytes(SIMULATION_ONLY_ENGINE_RPM_LENGTH, "little"),
        is_extended_id=True,
    )


def decode_simulated_engine_rpm(frame: CanFrame) -> int:
    if len(frame.data) != SIMULATION_ONLY_ENGINE_RPM_LENGTH:
        raise ValueError(
            "simulated engine RPM payload must be exactly "
            f"{SIMULATION_ONLY_ENGINE_RPM_LENGTH} bytes"
        )
    rpm = int.from_bytes(frame.data, "little")
    if rpm > MAX_SIMULATED_ENGINE_RPM:
        raise ValueError("simulated engine RPM payload is out of range")
    return rpm


def decode_simulated_speed(frame: CanFrame) -> float:
    if len(frame.data) != SIMULATION_ONLY_SPEED_LENGTH:
        raise ValueError(
            f"simulated speed payload must be exactly {SIMULATION_ONLY_SPEED_LENGTH} bytes"
        )
    return int.from_bytes(frame.data, "little") / 10.0


def encode_simulated_oil_temperature(temperature_c: float) -> CanFrame:
    return _encode_simulated_temperature(
        SIMULATION_ONLY_OIL_TEMPERATURE_ID,
        temperature_c,
    )


def encode_simulated_coolant_temperature(temperature_c: float) -> CanFrame:
    return _encode_simulated_temperature(
        SIMULATION_ONLY_COOLANT_TEMPERATURE_ID,
        temperature_c,
    )


def decode_simulated_temperature(frame: CanFrame) -> float:
    if len(frame.data) != SIMULATION_ONLY_TEMPERATURE_LENGTH:
        raise ValueError(
            "simulated temperature payload must be exactly "
            f"{SIMULATION_ONLY_TEMPERATURE_LENGTH} bytes"
        )
    temperature_c = int.from_bytes(frame.data, "little", signed=True) / 10.0
    if not MIN_SIMULATED_TEMPERATURE_C <= temperature_c <= MAX_SIMULATED_TEMPERATURE_C:
        raise ValueError("simulated temperature payload is out of range")
    return temperature_c


def _encode_simulated_temperature(arbitration_id: int, temperature_c: float) -> CanFrame:
    if (
        isinstance(temperature_c, bool)
        or not isinstance(temperature_c, (int, float))
        or not math.isfinite(temperature_c)
    ):
        raise ValueError("simulated temperature must be a finite number")
    if not MIN_SIMULATED_TEMPERATURE_C <= temperature_c <= MAX_SIMULATED_TEMPERATURE_C:
        raise ValueError(
            "simulated temperature must be between "
            f"{MIN_SIMULATED_TEMPERATURE_C:g} and {MAX_SIMULATED_TEMPERATURE_C:g} C"
        )
    temperature_deci_c = round(temperature_c * 10)
    return CanFrame(
        arbitration_id,
        temperature_deci_c.to_bytes(
            SIMULATION_ONLY_TEMPERATURE_LENGTH,
            "little",
            signed=True,
        ),
        is_extended_id=True,
    )


SignalDecoder = Callable[[CanFrame, float, CanNetwork], ApplicationEvent]


@dataclass(frozen=True)
class VehicleSignalSpec:
    network: CanNetwork
    arbitration_id: int
    encode: Callable[..., CanFrame]
    decode: SignalDecoder


def _signal(
    network: CanNetwork,
    arbitration_id: int,
    encode: Callable[..., CanFrame],
    decode_value: Callable[[CanFrame], object],
    sample: Callable[..., object],
    event: Callable[..., ApplicationEvent],
) -> VehicleSignalSpec:
    return VehicleSignalSpec(
        network,
        arbitration_id,
        encode,
        lambda frame, at, source: event(sample(decode_value(frame), at, source)),
    )


VEHICLE_SIGNALS = {
    VehicleSignal.SPEED: _signal(
        CanNetwork.FCAN,
        SIMULATION_ONLY_SPEED_ID,
        encode_simulated_speed,
        decode_simulated_speed,
        SpeedSample,
        SpeedObserved,
    ),
    VehicleSignal.RPM: _signal(
        CanNetwork.PTCAN,
        SIMULATION_ONLY_ENGINE_RPM_ID,
        encode_simulated_engine_rpm,
        decode_simulated_engine_rpm,
        EngineRpmSample,
        EngineRpmObserved,
    ),
    VehicleSignal.OIL_TEMPERATURE: _signal(
        CanNetwork.PTCAN,
        SIMULATION_ONLY_OIL_TEMPERATURE_ID,
        encode_simulated_oil_temperature,
        decode_simulated_temperature,
        OilTemperatureSample,
        OilTemperatureObserved,
    ),
    VehicleSignal.COOLANT_TEMPERATURE: _signal(
        CanNetwork.PTCAN,
        SIMULATION_ONLY_COOLANT_TEMPERATURE_ID,
        encode_simulated_coolant_temperature,
        decode_simulated_temperature,
        CoolantTemperatureSample,
        CoolantTemperatureObserved,
    ),
}

class SimulationProtocolRouter(ProtocolRouter):
    """Add unmistakably synthetic messages to the normal project router."""

    def __init__(
        self,
        ids: CustomCanIds | None = None,
        *,
        button_input_enabled: bool = True,
        synthetic_speed_network: CanNetwork = CanNetwork.FCAN,
    ) -> None:
        super().__init__(ids, button_input_enabled=button_input_enabled)
        self._signal_decoders = {
            (
                synthetic_speed_network if signal is VehicleSignal.SPEED else spec.network,
                spec.arbitration_id,
            ): spec.decode
            for signal, spec in VEHICLE_SIGNALS.items()
        }

    def decode(
        self,
        routed: RoutedCanFrame,
        observed_at: float,
    ) -> ApplicationEvent | RegistryHelloObserved | RegistryHeartbeatObserved | None:
        event = super().decode(routed, observed_at)
        if event is not None:
            return event
        frame = routed.frame
        if not frame.is_extended_id:
            return None
        decoder = self._signal_decoders.get((routed.network, frame.arbitration_id))
        return None if decoder is None else decoder(frame, observed_at, routed.network)
