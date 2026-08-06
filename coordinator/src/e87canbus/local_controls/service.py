"""Bounded single-owner lifecycle for the coordinator's local controls."""

from __future__ import annotations

import queue
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum

from e87canbus.local_controls.model import (
    ActivateHotspot,
    DeactivateHotspot,
    HotspotAdapterFailed,
    InboxOverloaded,
    LocalControlsEffect,
    LocalControlsEvent,
    LocalControlsState,
    OwnerFailed,
    PanelAdapterFailed,
    PanelRefreshDue,
    SetPanelDisplay,
    ShutdownRequested,
    reduce_local_controls,
)
from e87canbus.local_controls.ports import (
    Clock,
    CoordinatorConditionPort,
    HotspotPort,
    PanelPort,
)


class LocalControlsServiceError(RuntimeError):
    pass


class LocalControlsNotRunning(LocalControlsServiceError):
    pass


class LocalControlsInboxFull(LocalControlsServiceError):
    pass


class LocalControlsLifecycle(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"


@dataclass(frozen=True)
class LocalControlsSnapshot:
    boot_id: str
    revision: int
    state: LocalControlsState


LocalControlsNotification = Callable[[LocalControlsSnapshot], None]


@dataclass(frozen=True)
class _QueuedEvent:
    event: LocalControlsEvent
    future: Future[int] | None


class LocalControlsService:
    """Own the local panel and hotspot without sharing controller timing or state."""

    _START_TIMEOUT_S = 5.0
    _STOP_TIMEOUT_S = 5.0

    def __init__(
        self,
        *,
        panel: PanelPort,
        hotspot: HotspotPort,
        coordinator_condition: CoordinatorConditionPort,
        clock: Clock = time.monotonic,
        inbox_capacity: int = 32,
        poll_interval_s: float = 0.05,
        panel_refresh_interval_s: float = 0.5,
    ) -> None:
        if inbox_capacity < 1:
            raise ValueError("inbox_capacity must be positive")
        if poll_interval_s <= 0 or panel_refresh_interval_s <= 0:
            raise ValueError("service intervals must be positive")
        self._panel = panel
        self._hotspot = hotspot
        self._coordinator_condition = coordinator_condition
        self._clock = clock
        self._poll_interval_s = poll_interval_s
        self._panel_refresh_interval_s = panel_refresh_interval_s
        self._inbox: queue.Queue[_QueuedEvent] = queue.Queue(maxsize=inbox_capacity)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._lifecycle = LocalControlsLifecycle.CREATED
        self._accepting = False
        self._thread: threading.Thread | None = None
        self._notification: LocalControlsNotification | None = None
        self._boot_id: str | None = None
        self._revision = 0
        self._state = LocalControlsState()
        self._snapshot: LocalControlsSnapshot | None = None
        self._failure: BaseException | None = None
        self._overflow_latched = False
        self._graceful_stop = True

    @property
    def lifecycle(self) -> LocalControlsLifecycle:
        with self._lock:
            return self._lifecycle

    @property
    def inbox_capacity(self) -> int:
        return self._inbox.maxsize

    @property
    def inbox_depth(self) -> int:
        return self._inbox.qsize()

    @property
    def failure(self) -> BaseException | None:
        with self._lock:
            return self._failure

    def snapshot(self) -> LocalControlsSnapshot:
        with self._lock:
            if self._snapshot is None:
                raise LocalControlsNotRunning("local-controls service has not started")
            return self._snapshot

    def start(self, notification: LocalControlsNotification | None = None) -> None:
        with self._lock:
            if self._lifecycle is not LocalControlsLifecycle.CREATED:
                raise LocalControlsServiceError(
                    "local-controls service may be started exactly once"
                )
            self._boot_id = uuid.uuid4().hex
            self._notification = notification
            startup: Future[None] = Future()
            self._thread = threading.Thread(
                target=self._run,
                args=(startup,),
                name="local-controls-owner",
            )
            self._thread.start()
        startup.result(timeout=self._START_TIMEOUT_S)

    def submit(self, event: LocalControlsEvent) -> Future[int]:
        future: Future[int] = Future()
        with self._lock:
            if not self._accepting:
                raise LocalControlsNotRunning("local-controls service is not accepting input")
            try:
                self._inbox.put_nowait(_QueuedEvent(event, future))
            except queue.Full as exc:
                self._overflow_latched = True
                raise LocalControlsInboxFull("local-controls inbox is full") from exc
        return future

    def submit_input(self, event: LocalControlsEvent) -> bool:
        with self._lock:
            if not self._accepting:
                return False
            try:
                self._inbox.put_nowait(_QueuedEvent(event, None))
            except queue.Full:
                self._overflow_latched = True
                return False
        return True

    def stop(self, *, graceful: bool = True) -> None:
        with self._lock:
            if self._lifecycle is LocalControlsLifecycle.CREATED:
                self._lifecycle = LocalControlsLifecycle.STOPPED
                return
            if self._lifecycle is LocalControlsLifecycle.STOPPED:
                return
            self._graceful_stop = graceful
            self._accepting = False
            self._stop.set()
            thread = self._thread
        assert thread is not None
        thread.join(timeout=self._STOP_TIMEOUT_S)
        if thread.is_alive():
            raise LocalControlsServiceError("local-controls owner did not stop cleanly")

    def _run(self, startup: Future[None]) -> None:
        started = False
        try:
            self._start_owner()
            startup.set_result(None)
            started = True
            self._run_owner_loop()
        except Exception as exc:
            self._handle_owner_exception(startup, exc)
        finally:
            self._finish_owner(started)

    def _start_owner(self) -> None:
        with self._lock:
            self._accepting = True
        self._panel.start(self.submit_input)
        self._hotspot.start(self.submit_input)
        self._coordinator_condition.start(self.submit_input)
        with self._lock:
            self._lifecycle = LocalControlsLifecycle.RUNNING
        self._record(force=True)
        self._apply_effects((SetPanelDisplay(self._state.desired_display),))

    def _run_owner_loop(self) -> None:
        next_poll = self._clock()
        next_refresh = next_poll + self._panel_refresh_interval_s
        while not self._stop.is_set():
            queued = self._next_queued_event(next_poll, next_refresh)
            if queued is not None:
                self._process_queued_event(queued)
            if self._take_overflow():
                self._process(InboxOverloaded(self._inbox.maxsize))
            next_poll, next_refresh = self._run_due_work(next_poll, next_refresh)

    def _next_queued_event(
        self,
        next_poll: float,
        next_refresh: float,
    ) -> _QueuedEvent | None:
        now = self._clock()
        timeout = min(
            max(min(next_poll, next_refresh) - now, 0.0),
            self._poll_interval_s,
        )
        try:
            return self._inbox.get(timeout=timeout)
        except queue.Empty:
            return None

    def _process_queued_event(self, queued: _QueuedEvent) -> None:
        try:
            revision = self._process(queued.event)
        except Exception as exc:
            if queued.future is None:
                raise
            queued.future.set_exception(exc)
        else:
            if queued.future is not None:
                queued.future.set_result(revision)
        finally:
            self._inbox.task_done()

    def _run_due_work(self, next_poll: float, next_refresh: float) -> tuple[float, float]:
        now = self._clock()
        if now >= next_poll:
            self._poll_adapters(now)
            next_poll = now + self._poll_interval_s
        if now >= next_refresh:
            self._process(PanelRefreshDue())
            next_refresh = now + self._panel_refresh_interval_s
        return next_poll, next_refresh

    def _handle_owner_exception(self, startup: Future[None], failure: Exception) -> None:
        if startup.done():
            self._record_failure(failure)
        else:
            startup.set_exception(failure)

    def _finish_owner(self, started: bool) -> None:
        with self._lock:
            self._accepting = False
        if started and self._graceful_stop:
            self._process(ShutdownRequested())
        self._fail_pending()
        for port in (self._coordinator_condition, self._hotspot, self._panel):
            # A local peripheral must not turn application shutdown into a process fault.
            with suppress(Exception):
                port.close()
        with self._lock:
            self._lifecycle = LocalControlsLifecycle.STOPPED

    def _record_failure(self, failure: BaseException) -> None:
        self._graceful_stop = False
        with self._lock:
            if self._failure is None:
                self._failure = failure
        transition = reduce_local_controls(self._state, OwnerFailed(str(failure)))
        self._state = transition.state
        # Snapshot recording happens before notification. If the notification itself caused
        # the owner failure, the fault is still retained for reconnect and diagnostics.
        with suppress(Exception):
            self._record()
        with suppress(Exception):
            self._panel.set_display(self._state.desired_display)

    def _process(self, event: LocalControlsEvent) -> int:
        transition = reduce_local_controls(self._state, event)
        changed = transition.state != self._state
        self._state = transition.state
        if changed:
            self._record()
        self._apply_effects(transition.effects)
        with self._lock:
            return self._revision

    def _apply_effects(self, effects: tuple[LocalControlsEffect, ...]) -> None:
        for effect in effects:
            try:
                self._apply_effect(effect)
            except Exception as exc:
                self._handle_effect_failure(effect, exc)
                return

    def _apply_effect(self, effect: LocalControlsEffect) -> None:
        if isinstance(effect, SetPanelDisplay):
            self._panel.set_display(effect.display)
        elif isinstance(effect, ActivateHotspot):
            self._hotspot.activate()
        elif isinstance(effect, DeactivateHotspot):
            self._hotspot.deactivate()

    def _handle_effect_failure(
        self,
        effect: LocalControlsEffect,
        failure: Exception,
    ) -> None:
        event: LocalControlsEvent = (
            PanelAdapterFailed(str(failure))
            if isinstance(effect, SetPanelDisplay)
            else HotspotAdapterFailed(str(failure))
        )
        transition = reduce_local_controls(self._state, event)
        if transition.state != self._state:
            self._state = transition.state
            self._record()
        # The fault transition replaces the interrupted command; remaining effects from the
        # original transition could otherwise overwrite it with stale optimistic state.
        self._apply_effects(transition.effects)

    def _poll_adapters(self, now: float) -> None:
        for port, failure_type in (
            (self._panel, PanelAdapterFailed),
            (self._hotspot, HotspotAdapterFailed),
        ):
            try:
                port.poll(now)
            except Exception as exc:
                self._process(failure_type(str(exc)))
        # The condition adapter is application composition, not a fallible peripheral.
        self._coordinator_condition.poll(now)

    def _record(self, *, force: bool = False) -> None:
        with self._lock:
            if not force and self._snapshot is not None and self._snapshot.state == self._state:
                return
            self._revision += 1
            assert self._boot_id is not None
            snapshot = LocalControlsSnapshot(self._boot_id, self._revision, self._state)
            self._snapshot = snapshot
            notification = self._notification
        if notification is not None:
            notification(snapshot)

    def _take_overflow(self) -> bool:
        with self._lock:
            overflow = self._overflow_latched
            self._overflow_latched = False
            return overflow

    def _fail_pending(self) -> None:
        while True:
            try:
                queued = self._inbox.get_nowait()
            except queue.Empty:
                return
            if queued.future is not None:
                queued.future.set_exception(
                    LocalControlsNotRunning(
                        "local-controls service stopped before processing input"
                    )
                )
            self._inbox.task_done()
