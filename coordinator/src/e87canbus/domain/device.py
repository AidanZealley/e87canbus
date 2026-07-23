"""Repository-owned device vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from e87canbus.protocol.generated import CUSTOM_DEVICE_PROTOCOL_VERSION


class DeviceRole(StrEnum):
    BUTTON_PAD = "button_pad"
    SERVOTRONIC_CONTROLLER = "servotronic_controller"


class DeviceSource(StrEnum):
    PHYSICAL = "physical"
    EMULATED = "emulated"
    DISABLED = "disabled"


class DeviceLifecycleStatus(StrEnum):
    DISABLED = "disabled"
    NOT_FOUND = "not_found"
    PENDING = "pending"
    ACTIVE = "active"
    STALE = "stale"
    INCOMPATIBLE = "incompatible"
    FAULT = "fault"


@dataclass(frozen=True)
class DeviceIdentity:
    role: DeviceRole
    device_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.role, DeviceRole):
            raise ValueError("device identity role must be a DeviceRole")
        if type(self.device_id) is not int or not 0 <= self.device_id <= 0xFFFF:
            raise ValueError("device identity device_id must fit in an unsigned 16-bit value")


@dataclass(frozen=True)
class DeviceCatalogueEntry:
    identity: DeviceIdentity
    enabled: bool
    supported_protocol_version: int
    instance_limit: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.identity, DeviceIdentity):
            raise ValueError("device catalogue identity must be a DeviceIdentity")
        if type(self.enabled) is not bool:
            raise ValueError("device catalogue enabled must be a boolean")
        if (
            type(self.supported_protocol_version) is not int
            or not 0 <= self.supported_protocol_version <= 0x0F
        ):
            # WELCOME_ACK stores the controller version in its high nibble.
            raise ValueError("supported protocol version must fit in the ACK version nibble")
        if type(self.instance_limit) is not int or self.instance_limit < 1:
            raise ValueError("device catalogue instance_limit must be positive")


DEFAULT_DEVICE_CATALOGUE = (
    DeviceCatalogueEntry(
        identity=DeviceIdentity(DeviceRole.BUTTON_PAD, 1),
        enabled=True,
        supported_protocol_version=CUSTOM_DEVICE_PROTOCOL_VERSION,
    ),
    DeviceCatalogueEntry(
        identity=DeviceIdentity(DeviceRole.SERVOTRONIC_CONTROLLER, 1),
        enabled=True,
        supported_protocol_version=CUSTOM_DEVICE_PROTOCOL_VERSION,
    ),
)
