"""Bounded single-owner controller service lifecycle."""

from __future__ import annotations

import queue
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from e87canbus.application.controller import ApplicationSnapshot
from e87canbus.config import AppConfig
from e87canbus.runtime import DiagnosticSnapshot


class ControllerServiceError(RuntimeError):
    """Base error for controller-service lifecycle and submission failures."""


class ControllerServiceNotRunning(ControllerServiceError):
    """Raised when work is submitted outside the running lifecycle."""


class ControllerInboxFull(ControllerServiceError):
    """Raised when bounded runtime work cannot be accepted."""


class ControllerWorkUnavailable(ControllerServiceError):
    """Raised when selected runtime state cannot process otherwise valid work."""


class ControllerServiceLifecycle(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"


class ControllerMode(StrEnum):
    LIVE = "live"
    SIMULATED = "simulated"


@dataclass(frozen=True)
class RuntimeExecution:
    """One runtime operation and any ordered compatibility publications it produced."""

    result: object
    compatibility_snapshot: object
    events: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class ControllerCommandResult:
    """Boot-local revision committed for one matched semantic command."""

    revision: int
    controller_failed: bool


@dataclass(frozen=True)
class ControllerServiceSnapshot:
    """Immutable service-owned projection scoped to one opaque process boot."""

    boot_id: str
    revision: int
    application: ApplicationSnapshot
    diagnostics: DiagnosticSnapshot


RuntimeNotification = Callable[[RuntimeExecution], None]
RuntimeInputSink = Callable[[object], bool]


class ControllerRuntimeAdapter(Protocol):
    """Selected physical or simulated runtime behind the common owner loop."""

    @property
    def config(self) -> AppConfig: ...

    def start(self, submit_input: RuntimeInputSink) -> RuntimeExecution: ...

    def execute(self, work: object) -> RuntimeExecution: ...

    def timer(self, now: float) -> RuntimeExecution | None: ...

    def shutdown(self, now: float) -> RuntimeExecution | None: ...

    def projection(self) -> tuple[int, ApplicationSnapshot, DiagnosticSnapshot]: ...

    @property
    def terminal(self) -> bool: ...


@dataclass(frozen=True)
class _QueuedWork:
    value: object
    future: Future[object] | None


class ControllerService:
    """Own one runtime, bounded inbox, timer schedule and mutation thread."""

    _POLL_INTERVAL_S = 0.05
    _START_TIMEOUT_S = 5.0
    _STOP_TIMEOUT_S = 5.0

    def __init__(
        self,
        runtime: ControllerRuntimeAdapter,
        *,
        mode: ControllerMode,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._runtime = runtime
        self._mode = mode
        self._clock = clock
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
        self._latest_execution: RuntimeExecution | None = None
        self._latest_snapshot: ControllerServiceSnapshot | None = None
        self._failure: BaseException | None = None

    @property
    def config(self) -> AppConfig:
        return self._runtime.config

    @property
    def mode(self) -> ControllerMode:
        return self._mode

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
    def latest_compatibility_snapshot(self) -> object:
        with self._lock:
            if self._latest_execution is None:
                raise ControllerServiceNotRunning("controller service has not started")
            return self._latest_execution.compatibility_snapshot

    def snapshot(self) -> ControllerServiceSnapshot:
        with self._lock:
            if self._latest_snapshot is None:
                raise ControllerServiceNotRunning("controller service has not started")
            return self._latest_snapshot

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

    def submit(self, work: object) -> Future[object]:
        future: Future[object] = Future()
        with self._lock:
            if not self._accepting:
                raise ControllerServiceNotRunning("controller service is not accepting work")
            try:
                self._inbox.put_nowait(_QueuedWork(work, future))
            except queue.Full as exc:
                raise ControllerInboxFull("controller runtime inbox is full") from exc
        return future

    def submit_input(self, work: object) -> bool:
        """Submit adapter-originated input without exposing a completion future."""

        with self._lock:
            if self._stop.is_set() or self._lifecycle is ControllerServiceLifecycle.STOPPED:
                return False
            try:
                self._inbox.put_nowait(_QueuedWork(work, None))
            except queue.Full:
                return False
        return True

    def stop(self) -> None:
        with self._lock:
            if self._lifecycle is ControllerServiceLifecycle.CREATED:
                self._lifecycle = ControllerServiceLifecycle.STOPPED
                return
            if self._lifecycle is ControllerServiceLifecycle.STOPPED:
                failure = self._failure
                thread = None
            else:
                self._accepting = False
                self._stop.set()
                thread = self._thread
                failure = None
        if thread is not None:
            thread.join(timeout=self._STOP_TIMEOUT_S)
            if thread.is_alive():
                raise ControllerServiceError("controller owner did not stop cleanly")
            with self._lock:
                failure = self._failure
        if failure is not None:
            raise ControllerServiceError(
                f"controller service stopped with failure: {failure}"
            ) from failure

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
                timeout = min(
                    max(next_tick - self._clock(), 0.0),
                    self._POLL_INTERVAL_S,
                )
                try:
                    queued = self._inbox.get(timeout=timeout)
                except queue.Empty:
                    queued = None

                if queued is not None:
                    try:
                        execution = self._runtime.execute(queued.value)
                        self._record(execution)
                    except Exception as exc:
                        if queued.future is not None:
                            queued.future.set_exception(exc)
                    else:
                        if queued.future is not None:
                            queued.future.set_result(execution.result)
                    finally:
                        self._inbox.task_done()

                now = self._clock()
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

    def _record_failure(self, failure: BaseException) -> None:
        with self._lock:
            if self._failure is None:
                self._failure = failure

    def _record(self, execution: RuntimeExecution, *, notify: bool = True) -> None:
        revision, application, diagnostics = self._runtime.projection()
        with self._lock:
            self._latest_execution = execution
            assert self._boot_id is not None
            self._latest_snapshot = ControllerServiceSnapshot(
                boot_id=self._boot_id,
                revision=revision,
                application=application,
                diagnostics=diagnostics,
            )
            notification = self._notification
        if notify and notification is not None:
            notification(execution)

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
