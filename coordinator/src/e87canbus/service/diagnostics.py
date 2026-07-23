"""Immutable service-owned projection and diagnostics DTOs.

These describe what the controller service publishes: adapter observations, inbox
and persistence/publisher health, and the boot-scoped composite snapshot. They
carry no behaviour and never mutate controller state.
"""

from __future__ import annotations

from dataclasses import dataclass

from e87canbus.application.controller import ApplicationSnapshot
from e87canbus.config import CanNetwork
from e87canbus.device_registry import DeviceRegistryEntry
from e87canbus.kernel import DiagnosticSnapshot, StateTopic
from e87canbus.protocol.servotronic_protocol import (
    CONTROL_MODE_WIRE,
    CURVE_SOURCE_WIRE,
    ServotronicStatus,
    inhibit_reason_wire,
)


@dataclass(frozen=True)
class RuntimeExecution:
    events: tuple[dict[str, object], ...] = ()
    changed_topics: frozenset[StateTopic] = frozenset()
    commit_count: int = 0


@dataclass(frozen=True)
class ObservedNetworkSnapshot:
    network: CanNetwork
    label: str
    interface: str
    bitrate: int
    connected: bool
    nodes: tuple[str, ...]


@dataclass(frozen=True)
class ObservedServotronicSnapshot:
    effective_assistance: float
    last_command_reason: str | None
    watchdog_timed_out: bool
    active_curve_source: str | None = None
    active_curve_revision: int | None = None
    active_curve_crc32: int | None = None
    observed_speed_kph: float | None = None
    speed_fresh: bool | None = None
    pwm_duty: int | None = None
    inhibit_reason: str | None = None


def observed_servotronic_snapshot(status: ServotronicStatus) -> ObservedServotronicSnapshot:
    """Project a physical controller status frame into the observed adapter snapshot.

    This is the single live-side conversion; the string spellings come from the canonical
    wire mappings so live, firmware, and the frontend stay identical.  The simulated runtime
    intentionally omits the physical-only fields (``active_curve_source`` and friends), so it
    builds its snapshot directly rather than routing through here.
    """

    return ObservedServotronicSnapshot(
        effective_assistance=status.assistance_per_mille / 1000,
        last_command_reason=CONTROL_MODE_WIRE[status.control_mode],
        watchdog_timed_out=False,
        active_curve_source=CURVE_SOURCE_WIRE[status.source],
        active_curve_revision=status.activation_revision,
        active_curve_crc32=status.curve_crc32,
        observed_speed_kph=status.speed_deci_kph / 10,
        speed_fresh=status.speed_fresh,
        pwm_duty=status.pwm_duty,
        inhibit_reason=inhibit_reason_wire(status.inhibit_reason),
    )


@dataclass(frozen=True)
class ObservedLightingSnapshot:
    """Adapter-owned observation of the vehicle high-beam output."""

    high_beam_enabled: bool | None


@dataclass(frozen=True)
class ControllerAdapterSnapshot:
    """Immutable adapter observations alongside the kernel-owned registry."""

    simulation_session_id: int | None
    registry: tuple[DeviceRegistryEntry, ...]
    networks: tuple[ObservedNetworkSnapshot, ...]
    servotronic: ObservedServotronicSnapshot | None
    lighting: ObservedLightingSnapshot | None = None


@dataclass(frozen=True)
class InboxDiagnostics:
    depth: int
    capacity: int
    current_latency_s: float
    latency_warning: bool
    overflow_latched: bool


@dataclass(frozen=True)
class PersistenceDiagnostics:
    available: bool
    fault: str | None


@dataclass(frozen=True)
class PublisherDiagnostics:
    running: bool
    failures: int
    trace_rows_dropped: int
    resource_changes_dropped: int
    transport_queue_saturations: int
    fault: str | None


@dataclass(frozen=True)
class ServiceDiagnostics:
    ready: bool
    inbox: InboxDiagnostics
    persistence: PersistenceDiagnostics
    publisher: PublisherDiagnostics


@dataclass(frozen=True)
class ControllerServiceSnapshot:
    """Immutable service-owned projection scoped to one opaque process boot."""

    boot_id: str
    revision: int
    topic_revisions: tuple[tuple[StateTopic, int], ...]
    application: ApplicationSnapshot
    diagnostics: DiagnosticSnapshot
    adapter: ControllerAdapterSnapshot
    service: ServiceDiagnostics
