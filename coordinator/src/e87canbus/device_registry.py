"""The controller-owned device registry and its pure lifecycle transitions."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from e87canbus.device import (
    DEFAULT_DEVICE_CATALOGUE,
    DeviceCatalogueEntry,
    DeviceLifecycleStatus,
    DeviceRole,
    DeviceSource,
)
from e87canbus.protocol.can import (
    DeviceHeartbeatPayload,
    DeviceHelloPayload,
    DeviceWelcomeAckPayload,
)

CONTACT_TIMEOUT_S = 3.0
INCOMPATIBLE_RETRY_S = 5.0
INCOMPATIBLE_OBSERVATION_TIMEOUT_S = 15.0
FEEDBACK_DURATION_S = 0.5


class FeatureUnavailable(RuntimeError):
    """A device-dependent operation cannot be accepted in the current composition."""

    def __init__(self, role: DeviceRole, status: DeviceLifecycleStatus, message: str) -> None:
        self.role = role
        self.status = status
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class RegistryHelloObserved:
    role: DeviceRole
    payload: DeviceHelloPayload
    observed_at: float

    def __post_init__(self) -> None:
        if not isinstance(self.role, DeviceRole):
            raise ValueError("registry HELLO role must be a DeviceRole")
        if not isinstance(self.payload, DeviceHelloPayload):
            raise ValueError("registry HELLO payload must be a DeviceHelloPayload")
        _require_time(self.observed_at, "registry HELLO observation time")


@dataclass(frozen=True)
class RegistryHeartbeatObserved:
    role: DeviceRole
    payload: DeviceHeartbeatPayload
    observed_at: float

    def __post_init__(self) -> None:
        if not isinstance(self.role, DeviceRole):
            raise ValueError("registry HEARTBEAT role must be a DeviceRole")
        if not isinstance(self.payload, DeviceHeartbeatPayload):
            raise ValueError("registry HEARTBEAT payload must be a DeviceHeartbeatPayload")
        _require_time(self.observed_at, "registry HEARTBEAT observation time")


@dataclass(frozen=True)
class DeviceRegistryEntry:
    """One immutable registry record; lease and sequence fields stay kernel-private."""

    role: DeviceRole
    label: str
    device_id: int
    source_mode: DeviceSource
    status: DeviceLifecycleStatus
    protocol_version: int | None = None
    device_session_id: int | None = None
    last_status_code: int | None = None
    last_transition_monotonic_s: float | None = None
    _last_hello_sequence: int | None = field(default=None, repr=False, compare=False)
    _last_heartbeat_sequence: int | None = field(default=None, repr=False, compare=False)
    _lease_deadline: float | None = field(default=None, repr=False, compare=False)
    _incompatible_deadline: float | None = field(default=None, repr=False, compare=False)
    _controller_session_id: int | None = field(default=None, repr=False, compare=False)
    _supported_protocol_version: int = field(default=0, repr=False, compare=False)
    _registered: bool = field(default=False, repr=False, compare=False)
    _last_contact_monotonic_s: float | None = field(default=None, repr=False, compare=False)

    @property
    def usable(self) -> bool:
        return self.status is DeviceLifecycleStatus.ACTIVE

    @property
    def last_contact_monotonic_s(self) -> float | None:
        """Internal adapter compatibility observation; not part of the public projection."""

        return self._last_contact_monotonic_s

    @property
    def next_deadline(self) -> float | None:
        deadlines = tuple(
            deadline
            for deadline in (self._lease_deadline, self._incompatible_deadline)
            if deadline is not None
        )
        return min(deadlines) if deadlines else None


@dataclass(frozen=True)
class RegistryTransition:
    entry: DeviceRegistryEntry
    acknowledgement: DeviceWelcomeAckPayload | None = None
    accepted: bool = False


def initial_registry(
    sources: Mapping[DeviceRole, DeviceSource] | None = None,
) -> tuple[DeviceRegistryEntry, ...]:
    selected_sources = sources or {}
    return tuple(
        _initial_entry(entry, selected_sources.get(entry.identity.role, DeviceSource.PHYSICAL))
        for entry in DEFAULT_DEVICE_CATALOGUE
    )


def registry_entry(
    entries: tuple[DeviceRegistryEntry, ...], role: DeviceRole
) -> DeviceRegistryEntry:
    return next(entry for entry in entries if entry.role is role)


def transition_hello(
    entry: DeviceRegistryEntry,
    observation: RegistryHelloObserved,
    controller_session_id: int,
) -> RegistryTransition:
    """Apply one decoded HELLO without mutating the owning kernel."""

    if entry.status is DeviceLifecycleStatus.DISABLED:
        return RegistryTransition(entry)
    payload = observation.payload
    if payload.device_id != entry.device_id:
        return RegistryTransition(entry)

    acknowledgement = DeviceWelcomeAckPayload(
        controller_protocol_version=entry_protocol_version(entry),
        response_code=(0 if payload.protocol_version == entry_protocol_version(entry) else 1),
        device_id=payload.device_id,
        device_session_id=payload.device_session_id,
        controller_session_id=controller_session_id,
        device_sequence=payload.sequence,
    )
    if payload.protocol_version != entry_protocol_version(entry):
        if (
            entry.device_session_id == payload.device_session_id
            and entry._last_hello_sequence is not None
            and _sequence_is_older(payload.sequence, entry._last_hello_sequence)
        ):
            return RegistryTransition(entry)
        next_entry = replace(
            entry,
            status=DeviceLifecycleStatus.INCOMPATIBLE,
            protocol_version=payload.protocol_version,
            device_session_id=payload.device_session_id,
            last_status_code=None,
            last_transition_monotonic_s=(
                entry.last_transition_monotonic_s
                if entry.status is DeviceLifecycleStatus.INCOMPATIBLE
                else observation.observed_at
            ),
            _last_hello_sequence=payload.sequence,
            _last_heartbeat_sequence=None,
            _lease_deadline=None,
            _incompatible_deadline=observation.observed_at + INCOMPATIBLE_OBSERVATION_TIMEOUT_S,
            _controller_session_id=controller_session_id,
            _registered=False,
            _last_contact_monotonic_s=observation.observed_at,
        )
        return RegistryTransition(next_entry, acknowledgement, accepted=True)

    same_session = entry.device_session_id == payload.device_session_id
    if (
        same_session
        and entry._last_hello_sequence is not None
        and _sequence_is_older(payload.sequence, entry._last_hello_sequence)
    ):
        return RegistryTransition(entry)
    should_enter_pending = not same_session or entry.status in {
        DeviceLifecycleStatus.NOT_FOUND,
        DeviceLifecycleStatus.STALE,
        DeviceLifecycleStatus.INCOMPATIBLE,
    }
    next_entry = replace(
        entry,
        status=DeviceLifecycleStatus.PENDING if should_enter_pending else entry.status,
        protocol_version=payload.protocol_version,
        device_session_id=payload.device_session_id,
        last_status_code=(None if should_enter_pending else entry.last_status_code),
        last_transition_monotonic_s=(
            observation.observed_at
            if should_enter_pending and entry.status is not DeviceLifecycleStatus.PENDING
            else entry.last_transition_monotonic_s
        ),
        _last_hello_sequence=payload.sequence,
        _last_heartbeat_sequence=(None if not same_session else entry._last_heartbeat_sequence),
        _lease_deadline=observation.observed_at + CONTACT_TIMEOUT_S,
        _incompatible_deadline=None,
        _controller_session_id=controller_session_id,
        _registered=True,
        _last_contact_monotonic_s=observation.observed_at,
    )
    return RegistryTransition(next_entry, acknowledgement, accepted=True)


def transition_heartbeat(
    entry: DeviceRegistryEntry,
    observation: RegistryHeartbeatObserved,
    controller_session_id: int,
) -> RegistryTransition:
    """Apply one decoded HEARTBEAT after validating both sessions and sequence order."""

    if entry.status is DeviceLifecycleStatus.DISABLED:
        return RegistryTransition(entry)
    payload = observation.payload
    if (
        payload.device_id != entry.device_id
        or not entry._registered
        or payload.device_session_id != entry.device_session_id
        or payload.controller_session_id != controller_session_id
        or entry._controller_session_id != controller_session_id
    ):
        return RegistryTransition(entry)
    prior_sequence = entry._last_heartbeat_sequence
    if prior_sequence is not None and _sequence_is_older(payload.sequence, prior_sequence):
        return RegistryTransition(entry)

    next_status = (
        DeviceLifecycleStatus.ACTIVE if payload.status == 0 else DeviceLifecycleStatus.FAULT
    )
    next_entry = replace(
        entry,
        status=next_status,
        last_status_code=payload.status,
        last_transition_monotonic_s=(
            observation.observed_at
            if entry.status is not next_status
            else entry.last_transition_monotonic_s
        ),
        _last_heartbeat_sequence=payload.sequence,
        _lease_deadline=observation.observed_at + CONTACT_TIMEOUT_S,
        _last_contact_monotonic_s=observation.observed_at,
    )
    acknowledgement = DeviceWelcomeAckPayload(
        controller_protocol_version=entry_protocol_version(entry),
        response_code=0,
        device_id=payload.device_id,
        device_session_id=payload.device_session_id,
        controller_session_id=controller_session_id,
        device_sequence=payload.sequence,
    )
    return RegistryTransition(next_entry, acknowledgement, accepted=True)


def expire_entry(entry: DeviceRegistryEntry, now: float) -> DeviceRegistryEntry:
    """Expire one lease using injected monotonic time."""

    _require_time(now, "registry timeout time")
    if entry.status is DeviceLifecycleStatus.INCOMPATIBLE:
        deadline = entry._incompatible_deadline
        if deadline is not None and now >= deadline:
            return replace(
                entry,
                status=DeviceLifecycleStatus.STALE,
                last_transition_monotonic_s=now,
                _incompatible_deadline=None,
                _registered=False,
            )
        return entry
    deadline = entry._lease_deadline
    if (
        entry.status
        in {
            DeviceLifecycleStatus.PENDING,
            DeviceLifecycleStatus.ACTIVE,
            DeviceLifecycleStatus.FAULT,
        }
        and deadline is not None
        and now >= deadline
    ):
        return replace(
            entry,
            status=DeviceLifecycleStatus.STALE,
            last_transition_monotonic_s=now,
            _lease_deadline=None,
            _registered=False,
        )
    return entry


def entry_protocol_version(entry: DeviceRegistryEntry) -> int:
    return entry._supported_protocol_version


def _initial_entry(entry: DeviceCatalogueEntry, source: DeviceSource) -> DeviceRegistryEntry:
    status = (
        DeviceLifecycleStatus.DISABLED
        if source is DeviceSource.DISABLED or not entry.enabled
        else DeviceLifecycleStatus.NOT_FOUND
    )
    return DeviceRegistryEntry(
        role=entry.identity.role,
        label=_label_for(entry.identity.role),
        device_id=entry.identity.device_id,
        source_mode=source,
        status=status,
        _supported_protocol_version=entry.supported_protocol_version,
    )


def _label_for(role: DeviceRole) -> str:
    return {
        DeviceRole.BUTTON_PAD: "Button pad",
        DeviceRole.SERVOTRONIC_CONTROLLER: "Servotronic controller",
    }[role]


def _sequence_is_older(candidate: int, prior: int) -> bool:
    delta = (candidate - prior) % 256
    return 128 <= delta <= 255


def _require_time(value: float, name: str) -> None:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
