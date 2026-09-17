"""Bounded SSE publication for the local console browser."""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass, field

from e87canbus.console.models import (
    ConsoleCanState,
    ConsoleSnapshotData,
    ConsoleSnapshotEvent,
)
from e87canbus.console.service import ConsoleCanService, ConsoleServiceSnapshot

KEEPALIVE_INTERVAL_S = 15.0


@dataclass(eq=False, slots=True)
class _Subscriber:
    pending: deque[str]
    task: asyncio.Task[object]
    last_revision: int
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    closed: bool = False


class ConsoleSsePublisher:
    """Coalesce CAN activity and retain bounded output for each browser."""

    def __init__(
        self,
        service: ConsoleCanService,
        *,
        publication_interval_s: float = 1.0,
        client_capacity: int = 8,
        shutdown_timeout_s: float = 1.0,
    ) -> None:
        self._service = service
        self._publication_interval_s = publication_interval_s
        self._client_capacity = client_capacity
        self._shutdown_timeout_s = shutdown_timeout_s
        self._lock = threading.Lock()
        self._pending_snapshot: ConsoleServiceSnapshot | None = None
        self._urgent = False
        self._subscribers: set[_Subscriber] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wake: asyncio.Event | None = None
        self._wake_scheduled = False
        self._task: asyncio.Task[None] | None = None
        self._started = False
        self._stopping = False
        self._slow_disconnects = 0

    async def start(self) -> None:
        if self._started:
            raise RuntimeError("console SSE publisher may be started exactly once")
        self._started = True
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="console-sse-publisher")

    async def stop(self) -> None:
        self._stopping = True
        self._signal()
        task = self._task
        if task is not None:
            try:
                async with asyncio.timeout(self._shutdown_timeout_s):
                    await task
            except TimeoutError:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        self._close_all_subscribers()
        self._task = None
        with self._lock:
            self._pending_snapshot = None
        self._loop = None
        self._wake = None

    def offer(self, snapshot: ConsoleServiceSnapshot) -> None:
        """Accept the CAN receiver's complete latest state without waiting on a browser."""

        if self._stopping:
            return
        with self._lock:
            self._pending_snapshot = snapshot
            self._urgent = self._urgent or snapshot.fault is not None
        self._signal()

    async def events(
        self, request_task: asyncio.Task[object] | None = None
    ) -> AsyncIterator[str]:
        follows_consumer_task = request_task is None
        task = request_task or asyncio.current_task()
        if task is None:
            raise RuntimeError("console SSE subscription requires an asyncio task")
        subscriber = self._register(task)
        try:
            while True:
                with self._lock:
                    if follows_consumer_task:
                        task = asyncio.current_task()
                        assert task is not None
                        subscriber.task = task
                    if subscriber.closed:
                        return
                    if subscriber.pending:
                        payload = subscriber.pending.popleft()
                    else:
                        payload = None
                        subscriber.wake.clear()
                if payload is not None:
                    yield payload
                    continue
                try:
                    async with asyncio.timeout(KEEPALIVE_INTERVAL_S):
                        await subscriber.wake.wait()
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            self._unregister(subscriber)

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    @property
    def slow_disconnects(self) -> int:
        with self._lock:
            return self._slow_disconnects

    def _register(self, task: asyncio.Task[object]) -> _Subscriber:
        with self._lock:
            if not self.running or self._stopping:
                raise RuntimeError("console SSE publisher is not running")
            snapshot = self._service.snapshot()
            subscriber = _Subscriber(
                deque((_serialize(snapshot),)),
                task,
                last_revision=snapshot.revision,
            )
            self._subscribers.add(subscriber)
            return subscriber

    def _unregister(self, subscriber: _Subscriber) -> None:
        with self._lock:
            self._subscribers.discard(subscriber)
            subscriber.closed = True

    def _signal(self) -> None:
        with self._lock:
            loop = self._loop
            wake = self._wake
            if loop is None or wake is None or self._wake_scheduled:
                return
            self._wake_scheduled = True
        loop.call_soon_threadsafe(wake.set)

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        next_publication = loop.time()
        while True:
            with self._lock:
                pending = self._pending_snapshot is not None
                urgent = self._urgent
            now = loop.time()
            if pending and (urgent or now >= next_publication):
                self._flush()
                next_publication = loop.time() + self._publication_interval_s
                if self._stopping:
                    return
                continue
            if self._stopping:
                return

            wake = self._wake
            assert wake is not None
            timeout = max(next_publication - now, 0.0) if pending else None
            with suppress(TimeoutError):
                if timeout is None:
                    await wake.wait()
                else:
                    await asyncio.wait_for(wake.wait(), timeout=timeout)
            wake.clear()
            with self._lock:
                self._wake_scheduled = False

    def _flush(self) -> None:
        notifications: list[tuple[_Subscriber, bool]] = []
        with self._lock:
            snapshot = self._pending_snapshot
            self._pending_snapshot = None
            self._urgent = False
            if snapshot is not None:
                notifications = self._enqueue_locked(snapshot)
        for subscriber, terminate in notifications:
            self._notify_subscriber(subscriber, terminate=terminate)

    def _enqueue_locked(
        self, snapshot: ConsoleServiceSnapshot
    ) -> list[tuple[_Subscriber, bool]]:
        notifications: list[tuple[_Subscriber, bool]] = []
        payload = _serialize(snapshot)
        for subscriber in tuple(self._subscribers):
            if snapshot.revision <= subscriber.last_revision:
                continue
            saturated = len(subscriber.pending) >= self._client_capacity
            if saturated:
                subscriber.closed = True
                subscriber.pending.clear()
                self._subscribers.remove(subscriber)
                self._slow_disconnects += 1
            else:
                subscriber.pending.append(payload)
                subscriber.last_revision = snapshot.revision
            notifications.append((subscriber, saturated))
        return notifications

    def _close_all_subscribers(self) -> None:
        with self._lock:
            subscribers = tuple(self._subscribers)
            self._subscribers.clear()
            for subscriber in subscribers:
                subscriber.closed = True
                subscriber.pending.clear()
        for subscriber in subscribers:
            self._notify_subscriber(subscriber, terminate=True)

    def _notify_subscriber(self, subscriber: _Subscriber, *, terminate: bool) -> None:
        loop = self._loop
        if loop is None:
            return

        def notify() -> None:
            subscriber.wake.set()
            if terminate and not subscriber.task.done():
                subscriber.task.cancel()

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is loop:
            notify()
        else:
            loop.call_soon_threadsafe(notify)


def _serialize(snapshot: ConsoleServiceSnapshot) -> str:
    event = ConsoleSnapshotEvent(
        type="console.snapshot",
        data=ConsoleSnapshotData(
            can=ConsoleCanState(
                connected=snapshot.connected,
                frames_received=snapshot.frames_received,
                fault=snapshot.fault,
            )
        )
    )
    return f"data: {event.model_dump_json()}\n\n"
