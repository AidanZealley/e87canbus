"""Repository-owned device vocabulary and compatibility projections."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


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
            or not 0 <= self.supported_protocol_version <= 0xFF
        ):
            raise ValueError("supported protocol version must fit in one byte")
        if type(self.instance_limit) is not int or self.instance_limit < 1:
            raise ValueError("device catalogue instance_limit must be positive")


def validate_device_catalogue(
    catalogue: tuple[DeviceCatalogueEntry, ...],
) -> tuple[DeviceCatalogueEntry, ...]:
    """Validate the single-instance static role catalogue and return it unchanged."""

    if not isinstance(catalogue, tuple) or not catalogue:
        raise ValueError("device catalogue must be a non-empty tuple")
    if any(not isinstance(entry, DeviceCatalogueEntry) for entry in catalogue):
        raise ValueError("device catalogue entries must be DeviceCatalogueEntry values")
    identities = [entry.identity for entry in catalogue]
    roles = [identity.role for identity in identities]
    if len(set(identities)) != len(identities):
        raise ValueError("device catalogue identities must be unique")
    if len(set(roles)) != len(roles):
        raise ValueError("device catalogue may contain only one instance per role")
    return catalogue


DEFAULT_DEVICE_CATALOGUE = validate_device_catalogue(
    (
        DeviceCatalogueEntry(
            identity=DeviceIdentity(DeviceRole.BUTTON_PAD, 1),
            enabled=True,
            supported_protocol_version=1,
        ),
        DeviceCatalogueEntry(
            identity=DeviceIdentity(DeviceRole.SERVOTRONIC_CONTROLLER, 1),
            enabled=True,
            supported_protocol_version=1,
        ),
    )
)


@dataclass(frozen=True)
class DeviceProjection:
    """Pre-registry adapter projection retained until phase 3's live cutover.

    The service and current live contract are the concrete consumers. Phase 3 removes this
    compatibility projection when it introduces the registry entry contract; it is not a second
    application LED owner.
    """

    id: DeviceRole
    label: str
    source_mode: DeviceSource
    connected: bool | None
    last_seen_monotonic_s: float | None
    desired_led_colours: tuple[int, ...]
    observed_led_colours: tuple[int, ...] | None
    last_output_fault: str | None
