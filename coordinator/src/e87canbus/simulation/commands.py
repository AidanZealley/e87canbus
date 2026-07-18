"""Closed command vocabulary accepted by simulated vehicle and device adapters."""

from dataclasses import dataclass

from e87canbus.device import DeviceRole
from e87canbus.simulation.signals import VehicleSignal


@dataclass(frozen=True)
class PressButton:
    index: int


@dataclass(frozen=True)
class ReleaseButton:
    index: int


@dataclass(frozen=True)
class TapButton:
    index: int


@dataclass(frozen=True)
class RunControlTimer:
    now: float


@dataclass(frozen=True)
class SetVehicleSignal:
    signal: VehicleSignal
    value: int | float


@dataclass(frozen=True)
class SilenceVehicleSignal:
    signal: VehicleSignal


@dataclass(frozen=True)
class ResetSimulation:
    pass


@dataclass(frozen=True)
class ConnectSimulatedDevice:
    role: DeviceRole


@dataclass(frozen=True)
class DisconnectSimulatedDevice:
    role: DeviceRole


@dataclass(frozen=True)
class RebootSimulatedDevice:
    role: DeviceRole


def _require_device_role(role: DeviceRole) -> None:
    if not isinstance(role, DeviceRole):
        raise ValueError("role must be a DeviceRole")


def _require_byte(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFF:
        raise ValueError(f"{name} must be an unsigned byte")


@dataclass(frozen=True)
class SetSimulatedDeviceProtocolVersion:
    role: DeviceRole
    protocol_version: int

    def __post_init__(self) -> None:
        _require_device_role(self.role)
        _require_byte(self.protocol_version, "protocol_version")


@dataclass(frozen=True)
class SetSimulatedDeviceStatusCode:
    role: DeviceRole
    status_code: int

    def __post_init__(self) -> None:
        _require_device_role(self.role)
        _require_byte(self.status_code, "status_code")


SimulationCommand = (
    PressButton
    | ReleaseButton
    | TapButton
    | RunControlTimer
    | SetVehicleSignal
    | SilenceVehicleSignal
    | ResetSimulation
    | ConnectSimulatedDevice
    | DisconnectSimulatedDevice
    | RebootSimulatedDevice
    | SetSimulatedDeviceProtocolVersion
    | SetSimulatedDeviceStatusCode
)
