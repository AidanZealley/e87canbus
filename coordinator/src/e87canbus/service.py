"""Bounded single-owner controller service lifecycle."""

from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol

from e87canbus.application.controller import ApplicationSnapshot
from e87canbus.config import AppConfig, CanNetwork
from e87canbus.deployment import DeploymentSpec
from e87canbus.device import DeviceRole
from e87canbus.device_registry import DeviceRegistryEntry
from e87canbus.features.steering import ActiveSteeringCurve
from e87canbus.kernel import (
    DiagnosticSnapshot,
    InboxOverflowed,
    ReceivedCanFrame,
    StateTopic,
)
from e87canbus.servotronic_protocol import (
    CONTROL_MODE_WIRE,
    CURVE_SOURCE_WIRE,
    ServotronicStatus,
    inhibit_reason_wire,
)

LOGGER = logging.getLogger(__name__)


class ControllerServiceError(RuntimeError):
    """Base error for controller-service lifecycle and submission failures."""


class ControllerServiceNotRunning(ControllerServiceError):
    """Raised when work is submitted outside the running lifecycle."""


class ControllerInboxFull(ControllerServiceError):
    """Raised when bounded runtime work cannot be accepted."""


class ControllerWorkUnavailable(ControllerServiceError):
    """Raised when selected runtime state cannot process otherwise valid work."""


class SimulationDeviceUnavailable(ControllerWorkUnavailable):
    """Raised when a requested virtual peer is absent from the composition."""

    def __init__(self, role: DeviceRole) -> None:
        self.role = role
        super().__init__(f"simulated {role.value} is unavailable")


class ControllerServiceLifecycle(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"


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


RuntimeNotification = Callable[[RuntimeExecution], None]
RuntimeInputSink = Callable[[object], bool]


class ControllerRuntimeAdapter(Protocol):
    @property
    def config(self) -> AppConfig: ...

    def configure_initial_steering_curve(self, curve: ActiveSteeringCurve) -> None: ...

    def start(self, submit_input: RuntimeInputSink) -> RuntimeExecution: ...

    def execute(self, work: object) -> RuntimeExecution: ...

    def timer(self, now: float) -> RuntimeExecution | None: ...

    def next_deadline(self) -> float | None: ...

    def deadline(self, now: float) -> RuntimeExecution | None: ...

    def shutdown(self, now: float) -> RuntimeExecution | None: ...

    def close(self) -> None: ...

    def projection(
        self,
    ) -> tuple[ApplicationSnapshot, DiagnosticSnapshot, ControllerAdapterSnapshot]: ...

    @property
    def terminal(self) -> bool: ...


@dataclass(frozen=True)
class _QueuedWork:
    value: object
    future: Future[int] | None
    enqueued_at: float


class ControllerService:
    """Own one runtime, bounded inbox, timer schedule and mutation thread."""

    _POLL_INTERVAL_S = 0.05
    _START_TIMEOUT_S = 5.0
    _STOP_TIMEOUT_S = 5.0

    def __init__(
        self,
        runtime: ControllerRuntimeAdapter,
        *,
        deployment: DeploymentSpec,
        clock: Callable[[], float] = time.monotonic,
        load_persisted_steering_curve: bool = False,
    ) -> None:
        self._runtime = runtime
        self._deployment = deployment
        self._clock = clock
        self._load_persisted_steering_curve = load_persisted_steering_curve
        self._inbox: queue.Queue[_QueuedWork] = queue.Queue(
            maxsize=runtime.config.runtime_inbox_capacity
        )
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._lifecycle = ControllerServiceLifecycle.CREATED
        self._accepting = False
        self._thread: threading.Thread | None = None
        self._notification: RuntimeNotification | None = None
        self._boot_id: str | None = None
        self._latest_snapshot: ControllerServiceSnapshot | None = None
        self._revision = 0
        self._topic_revisions = {topic: 0 for topic in StateTopic}
        self._failure: BaseException | None = None
        self._ready = False
        self._current_queue_latency_s = 0.0
        self._queue_latency_warning = False
        self._overflow_latched: InboxOverflowed | None = None
        self._persistence = PersistenceDiagnostics(False, "not initialized")
        self._publisher = PublisherDiagnostics(
            running=False,
            failures=0,
            trace_rows_dropped=0,
            resource_changes_dropped=0,
            transport_queue_saturations=0,
            fault="not started",
        )
        self._stopped = threading.Event()
        self._fatal_exit = threading.Event()
        self._adapter_closed = False

    @property
    def config(self) -> AppConfig:
        return self._runtime.config

    @property
    def deployment(self) -> DeploymentSpec:
        return self._deployment

    @property
    def load_persisted_steering_curve(self) -> bool:
        return self._load_persisted_steering_curve

    @property
    def lifecycle(self) -> ControllerServiceLifecycle:
        with self._lock:
            return self._lifecycle

    @property
    def boot_id(self) -> str:
        with self._lock:
            if self._boot_id is None:
                raise ControllerServiceNotRunning("controller service has not started")
            return self._boot_id

    @property
    def inbox_depth(self) -> int:
        return self._inbox.qsize()

    @property
    def inbox_capacity(self) -> int:
        return self._inbox.maxsize

    @property
    def ready(self) -> bool:
        with self._lock:
            return self._is_ready_locked()

    @property
    def stopped_event(self) -> threading.Event:
        return self._stopped

    @property
    def fatal_exit_required(self) -> bool:
        return self._fatal_exit.is_set()

    def snapshot(self) -> ControllerServiceSnapshot:
        with self._lock:
            if self._latest_snapshot is None:
                raise ControllerServiceNotRunning("controller service has not started")
            return replace(self._latest_snapshot, service=self._service_diagnostics_locked())

    def mark_persistence_available(self) -> None:
        self._update_external_health(persistence=PersistenceDiagnostics(True, None))

    def configure_initial_steering_curve(self, curve: ActiveSteeringCurve) -> None:
        with self._lock:
            if self._lifecycle is not ControllerServiceLifecycle.CREATED:
                raise ControllerServiceError(
                    "initial steering curve must be configured before service startup"
                )
            self._runtime.configure_initial_steering_curve(curve)

    def mark_persistence_fault(self, message: str) -> None:
        self._update_external_health(persistence=PersistenceDiagnostics(False, message))

    def mark_ready(self) -> None:
        with self._lock:
            if self._lifecycle is not ControllerServiceLifecycle.RUNNING:
                raise ControllerServiceNotRunning("controller service is not running")
            self._ready = True
        self._refresh_external_health()

    def mark_not_ready(self) -> None:
        with self._lock:
            self._ready = False
        self._refresh_external_health()

    def update_publisher_health(
        self,
        diagnostics: PublisherDiagnostics,
    ) -> RuntimeExecution | None:
        return self._update_external_health(publisher=diagnostics, notify=False)

    def start(self, notification: RuntimeNotification | None = None) -> None:
        with self._lock:
            if self._lifecycle is not ControllerServiceLifecycle.CREATED:
                raise ControllerServiceError("controller service may be started exactly once")
            self._boot_id = uuid.uuid4().hex
            self._notification = notification
            startup: Future[None] = Future()
            self._thread = threading.Thread(
                target=self._run,
                args=(startup,),
                name="controller-owner",
            )
            self._thread.start()

        startup.result(timeout=self._START_TIMEOUT_S)

    def submit(self, work: object) -> Future[int]:
        future: Future[int] = Future()
        with self._lock:
            if not self._accepting:
                raise ControllerServiceNotRunning("controller service is not accepting work")
            try:
                self._inbox.put_nowait(_QueuedWork(work, future, self._clock()))
            except queue.Full as exc:
                self._latch_overflow_locked(work)
                raise ControllerInboxFull("controller runtime inbox is full") from exc
        return future

    def submit_input(self, work: object) -> bool:
        """Submit adapter-originated input without exposing a completion future."""

        with self._lock:
            if self._stop.is_set() or self._lifecycle is ControllerServiceLifecycle.STOPPED:
                return False
            try:
                self._inbox.put_nowait(_QueuedWork(work, None, self._clock()))
            except queue.Full:
                self._latch_overflow_locked(work)
                return False
        return True

    def stop(self, close_adapter: bool = True) -> None:
        with self._lock:
            if self._lifecycle is ControllerServiceLifecycle.CREATED:
                self._lifecycle = ControllerServiceLifecycle.STOPPED
                return
            if self._lifecycle is ControllerServiceLifecycle.STOPPED:
                failure = self._failure
                thread = None
            else:
                self._accepting = False
                self._ready = False
                self._stop.set()
                thread = self._thread
                failure = None
        if thread is not None:
            thread.join(timeout=self._STOP_TIMEOUT_S)
            if thread.is_alive():
                raise ControllerServiceError("controller owner did not stop cleanly")
            with self._lock:
                failure = self._failure
        if close_adapter:
            self.close_adapter()
        if failure is not None:
            raise ControllerServiceError(
                f"controller service stopped with failure: {failure}"
            ) from failure

    def close_adapter(self) -> None:
        with self._lock:
            if self._adapter_closed:
                return
            self._adapter_closed = True
        self._runtime.close()

    def _run(self, startup: Future[None]) -> None:
        try:
            initial = self._runtime.start(self.submit_input)
            self._record(initial)
            with self._lock:
                self._accepting = True
                self._lifecycle = ControllerServiceLifecycle.RUNNING
            startup.set_result(None)
            next_tick = self._clock() + self.config.tick_interval_s

            while not self._stop.is_set() and not self._runtime.terminal:
                with self._lock:
                    overflow = self._overflow_latched
                if overflow is not None:
                    execution = self._runtime.execute(overflow)
                    self._record(execution)
                    self._fatal_exit.set()
                    self._stop.set()
                    break
                now = self._clock()
                deadline = self._runtime.next_deadline()
                next_wakeup = next_tick if deadline is None else min(next_tick, deadline)
                timeout = min(max(next_wakeup - now, 0.0), self._POLL_INTERVAL_S)
                try:
                    queued = self._inbox.get(timeout=timeout)
                except queue.Empty:
                    queued = None

                if queued is not None:
                    try:
                        self._record_queue_latency(queued)
                        execution = self._runtime.execute(queued.value)
                        execution = replace(
                            execution,
                            changed_topics=execution.changed_topics | {StateTopic.HEALTH},
                        )
                        revision = self._record(execution)
                    except Exception as exc:
                        if queued.future is not None:
                            queued.future.set_exception(exc)
                    else:
                        if queued.future is not None:
                            with self._lock:
                                failed = bool(
                                    self._latest_snapshot
                                    and self._latest_snapshot.diagnostics.health.fatal
                                )
                            if failed:
                                queued.future.set_exception(
                                    ControllerWorkUnavailable(
                                        "controller entered a failed state while "
                                        "processing the command"
                                    )
                                )
                            else:
                                queued.future.set_result(revision)
                    finally:
                        self._inbox.task_done()

                now = self._clock()
                # Process an overdue phase before the periodic control tick.  The transition
                # receives the actual owner time, preserving the application's defined
                # overdue-deadline behavior rather than quantizing it to a control tick.
                deadline = self._runtime.next_deadline()
                if deadline is not None and now >= deadline and not self._runtime.terminal:
                    deadline_execution = self._runtime.deadline(now)
                    if deadline_execution is not None:
                        self._record(deadline_execution)
                if now >= next_tick and not self._runtime.terminal:
                    timer_execution = self._runtime.timer(now)
                    if timer_execution is not None:
                        self._record(timer_execution)
                    next_tick = now + self.config.tick_interval_s
        except Exception as exc:
            if not startup.done():
                startup.set_exception(exc)
            else:
                self._record_failure(exc)
        finally:
            with self._lock:
                self._accepting = False
                self._ready = False
            if self._runtime.terminal:
                self._fatal_exit.set()
            try:
                shutdown_execution = self._runtime.shutdown(self._clock())
                if shutdown_execution is not None:
                    self._record(shutdown_execution, notify=False)
            except Exception as exc:
                self._record_failure(exc)
            finally:
                self._fail_pending()
                with self._lock:
                    self._lifecycle = ControllerServiceLifecycle.STOPPED
                self._stopped.set()

    def _record_failure(self, failure: BaseException) -> None:
        with self._lock:
            if self._failure is None:
                self._failure = failure
            self._ready = False
        self._fatal_exit.set()

    def _record(
        self,
        execution: RuntimeExecution,
        *,
        notify: bool = True,
    ) -> int:
        application, diagnostics, adapter = self._runtime.projection()
        with self._lock:
            if self._latest_snapshot is None and not execution.changed_topics:
                execution = replace(execution, changed_topics=frozenset(StateTopic))
            revision_increment = execution.commit_count
            if revision_increment == 0 and execution.changed_topics:
                revision_increment = 1
            self._revision += revision_increment
            for topic in execution.changed_topics:
                self._topic_revisions[topic] = self._revision
            assert self._boot_id is not None
            self._latest_snapshot = ControllerServiceSnapshot(
                boot_id=self._boot_id,
                revision=self._revision,
                topic_revisions=tuple(self._topic_revisions.items()),
                application=application,
                diagnostics=diagnostics,
                adapter=adapter,
                service=self._service_diagnostics_locked(),
            )
            recorded_revision = self._revision
            notification = self._notification
        if notify and notification is not None:
            notification(execution)
        return recorded_revision

    def _fail_pending(self) -> None:
        while True:
            try:
                queued = self._inbox.get_nowait()
            except queue.Empty:
                return
            if queued.future is not None:
                queued.future.set_exception(
                    ControllerServiceNotRunning("controller service stopped before processing work")
                )
            self._inbox.task_done()

    def _record_queue_latency(self, queued: _QueuedWork) -> None:
        observed_at = (
            queued.value.received_at
            if isinstance(queued.value, ReceivedCanFrame)
            else queued.enqueued_at
        )
        latency = max(self._clock() - observed_at, 0.0)
        warning = latency > self.config.runtime_queue_latency_warning_s
        with self._lock:
            newly_warning = warning and not self._queue_latency_warning
            self._current_queue_latency_s = latency
            self._queue_latency_warning = warning
        if newly_warning:
            network = (
                queued.value.network.value
                if isinstance(queued.value, ReceivedCanFrame)
                else "service"
            )
            LOGGER.warning(
                "controller inbox latency warning: network=%s latency_s=%.3f",
                network,
                latency,
            )

    def _latch_overflow_locked(self, work: object) -> None:
        if self._overflow_latched is not None:
            return
        network = work.network if isinstance(work, ReceivedCanFrame) else None
        self._overflow_latched = InboxOverflowed(
            network,
            self._clock(),
            f"controller inbox capacity {self._inbox.maxsize} exceeded",
        )
        self._accepting = False

    def _service_diagnostics_locked(self) -> ServiceDiagnostics:
        return ServiceDiagnostics(
            ready=self._is_ready_locked(),
            inbox=InboxDiagnostics(
                depth=self._inbox.qsize(),
                capacity=self._inbox.maxsize,
                current_latency_s=self._current_queue_latency_s,
                latency_warning=self._queue_latency_warning,
                overflow_latched=self._overflow_latched is not None,
            ),
            persistence=self._persistence,
            publisher=self._publisher,
        )

    def _is_ready_locked(self) -> bool:
        return (
            self._ready
            and self._lifecycle is ControllerServiceLifecycle.RUNNING
            and self._persistence.available
            and (
                self._latest_snapshot is None or not self._latest_snapshot.diagnostics.health.fatal
            )
        )

    def _update_external_health(
        self,
        *,
        persistence: PersistenceDiagnostics | None = None,
        publisher: PublisherDiagnostics | None = None,
        notify: bool = True,
    ) -> RuntimeExecution | None:
        with self._lock:
            if persistence is not None:
                self._persistence = persistence
            if publisher is not None:
                self._publisher = publisher
        return self._refresh_external_health(notify=notify)

    def _refresh_external_health(
        self,
        *,
        notify: bool = True,
    ) -> RuntimeExecution | None:
        """Commit one service-health revision and optionally notify its publisher."""

        with self._lock:
            if self._latest_snapshot is None:
                return None
            service = self._service_diagnostics_locked()
            if self._latest_snapshot.service == service:
                return None
            self._revision += 1
            self._topic_revisions[StateTopic.HEALTH] = self._revision
            self._latest_snapshot = replace(
                self._latest_snapshot,
                revision=self._revision,
                topic_revisions=tuple(self._topic_revisions.items()),
                service=service,
            )
            execution = RuntimeExecution(
                changed_topics=frozenset({StateTopic.HEALTH}),
            )
            notification = self._notification
        if notify and notification is not None:
            notification(execution)
        return execution
