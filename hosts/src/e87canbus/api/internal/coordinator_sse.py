"""Bounded coordinator browser SSE publication."""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass, field

from e87canbus.api.models.coordinator_live import (
    ButtonsEvent,
    CoordinatorLiveEvent,
    EngineEvent,
    HealthEvent,
    SteeringEvent,
    VehicleEvent,
    coordinator_health_state,
    resource_changed_event,
    snapshot_event,
)
from e87canbus.api.models.live import (
    buttons_state,
    engine_state,
    steering_state,
    vehicle_state,
)
from e87canbus.api.models.resources import ResourceChangedEvent
from e87canbus.config import AppConfig
from e87canbus.kernel import StateTopic
from e87canbus.service import ControllerLoop, ControllerLoopSnapshot, RuntimeExecution

KEEPALIVE_INTERVAL_S = 15.0
TELEMETRY_TOPICS = frozenset({StateTopic.VEHICLE, StateTopic.ENGINE})
SSE_TOPICS = frozenset(
    {
        StateTopic.VEHICLE,
        StateTopic.ENGINE,
        StateTopic.STEERING,
        StateTopic.BUTTONS,
        StateTopic.HEALTH,
    }
)


@dataclass(eq=False, slots=True)
class _Subscriber:
    pending: deque[str]
    task: asyncio.Task[object]
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    closed: bool = False


class CoordinatorSsePublisher:
    """Rate-limit projections and retain bounded output for each browser."""

    def __init__(self, service: ControllerLoop, config: AppConfig) -> None:
        self._service = service
        self._telemetry_interval_s = 1.0 / config.live_publication.telemetry_hz
        self._health_interval_s = 1.0 / config.live_publication.health_hz
        self._client_capacity = config.live_publication.client_queue_capacity
        self._shutdown_timeout_s = config.live_publication.shutdown_timeout_s
        self._lock = threading.Lock()
        self._pending_topics: dict[StateTopic, ControllerLoopSnapshot] = {}
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
            raise RuntimeError("coordinator SSE publisher may be started exactly once")
        self._started = True
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="coordinator-sse-publisher")
        self._wake.set()

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
            self._pending_topics.clear()
        self._loop = None
        self._wake = None

    def offer(self, execution: RuntimeExecution) -> None:
        """Accept one controller-owner notification without waiting on a browser."""

        changed_topics = execution.changed_topics & SSE_TOPICS
        if not changed_topics or self._stopping:
            return
        snapshot = self._service.snapshot()
        with self._lock:
            for topic in changed_topics:
                self._pending_topics[topic] = snapshot
        self._signal()

    def offer_resource(self, event: ResourceChangedEvent) -> None:
        if self._stopping:
            return
        self._publish(resource_changed_event(event))

    async def events(
        self, request_task: asyncio.Task[object] | None = None
    ) -> AsyncIterator[str]:
        follows_consumer_task = request_task is None
        task = request_task or asyncio.current_task()
        if task is None:
            raise RuntimeError("coordinator SSE subscription requires an asyncio task")
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
                raise RuntimeError("coordinator SSE publisher is not running")
            subscriber = _Subscriber(deque(), task)
            subscriber.pending.append(_serialize(snapshot_event(self._service.snapshot())))
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
        next_telemetry = loop.time()
        next_health = loop.time()
        while True:
            now = loop.time()
            timeout = max(min(next_telemetry, next_health) - now, 0.0)
            wake = self._wake
            assert wake is not None
            with suppress(TimeoutError):
                await asyncio.wait_for(wake.wait(), timeout=timeout)
            wake.clear()
            with self._lock:
                self._wake_scheduled = False

            now = loop.time()
            telemetry_due = now >= next_telemetry
            health_due = now >= next_health
            self._flush(telemetry_due=telemetry_due, health_due=health_due)
            if self._stopping:
                return
            if telemetry_due:
                next_telemetry = now + self._telemetry_interval_s
            if health_due:
                next_health = now + self._health_interval_s

    def _flush(self, *, telemetry_due: bool, health_due: bool) -> None:
        notifications: list[tuple[_Subscriber, bool]] = []
        with self._lock:
            selected = {
                topic: snapshot
                for topic, snapshot in self._pending_topics.items()
                if (
                    (topic is StateTopic.HEALTH and health_due)
                    or (topic in TELEMETRY_TOPICS and telemetry_due)
                    or (topic not in TELEMETRY_TOPICS and topic is not StateTopic.HEALTH)
                )
            }
            for topic in selected:
                self._pending_topics.pop(topic, None)
            for topic, snapshot in selected.items():
                notifications.extend(
                    self._enqueue_locked(_serialize(_topic_event(topic, snapshot)))
                )
        for subscriber, terminate in notifications:
            self._notify_subscriber(subscriber, terminate=terminate)

    def _publish(self, event: CoordinatorLiveEvent) -> None:
        payload = _serialize(event)
        with self._lock:
            notifications = self._enqueue_locked(payload)
        for subscriber, terminate in notifications:
            self._notify_subscriber(subscriber, terminate=terminate)

    def _enqueue_locked(self, payload: str) -> list[tuple[_Subscriber, bool]]:
        notifications: list[tuple[_Subscriber, bool]] = []
        for subscriber in tuple(self._subscribers):
            saturated = len(subscriber.pending) >= self._client_capacity
            if saturated:
                subscriber.closed = True
                subscriber.pending.clear()
                self._subscribers.remove(subscriber)
                self._slow_disconnects += 1
            else:
                subscriber.pending.append(payload)
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
        if loop is not None:

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


def _serialize(event: CoordinatorLiveEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"


def _topic_event(topic: StateTopic, snapshot: ControllerLoopSnapshot) -> CoordinatorLiveEvent:
    if topic is StateTopic.VEHICLE:
        return VehicleEvent(type="vehicle", data=vehicle_state(snapshot))
    if topic is StateTopic.ENGINE:
        return EngineEvent(type="engine", data=engine_state(snapshot))
    if topic is StateTopic.STEERING:
        return SteeringEvent(type="steering", data=steering_state(snapshot))
    if topic is StateTopic.BUTTONS:
        return ButtonsEvent(type="buttons", data=buttons_state(snapshot))
    if topic is StateTopic.HEALTH:
        return HealthEvent(type="health", data=coordinator_health_state(snapshot))
    raise AssertionError(f"unhandled coordinator SSE topic: {topic}")
