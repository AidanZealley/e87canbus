"""Immutable service-owned projection and diagnostics DTOs.

These describe what the controller service publishes: inbox and
persistence/publisher health, and the boot-scoped composite snapshot. They
carry no behaviour and never mutate controller state.
"""

from __future__ import annotations

from dataclasses import dataclass

from e87canbus.domain.controller import ApplicationSnapshot
from e87canbus.kernel import DiagnosticSnapshot, StateTopic


@dataclass(frozen=True)
class RuntimeExecution:
    changed_topics: frozenset[StateTopic] = frozenset()
    commit_count: int = 0


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
class ControllerLoopSnapshot:
    """Immutable service-owned projection scoped to one opaque process boot."""

    boot_id: str
    revision: int
    topic_revisions: tuple[tuple[StateTopic, int], ...]
    application: ApplicationSnapshot
    diagnostics: DiagnosticSnapshot
    simulation_session_id: int | None
    service: ServiceDiagnostics
