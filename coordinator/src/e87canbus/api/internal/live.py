"""Bounded Socket.IO live-state publication."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

import socketio  # type: ignore[import-untyped]

from e87canbus.api.models.live import (
    LiveData,
    LiveEnvelope,
    TraceBatchData,
    TraceRow,
    buttons_state,
    devices_state,
    engine_state,
    health_state,
    snapshot_data,
    steering_state,
    vehicle_state,
)
from e87canbus.api.models.resources import ResourceChangedEvent
from e87canbus.config import AppConfig
from e87canbus.runtime import StateTopic
from e87canbus.service import (
    ControllerService,
    ControllerServiceSnapshot,
    PublisherDiagnostics,
    RuntimeExecution,
)

LOGGER = logging.getLogger(__name__)
TRACE_ROOM = "trace-subscribers"
TELEMETRY_TOPICS = frozenset({StateTopic.VEHICLE, StateTopic.ENGINE})
TOPIC_EVENTS = {
    StateTopic.VEHICLE: "vehicle.state",
    StateTopic.ENGINE: "engine.state",
    StateTopic.STEERING: "steering.state",
    StateTopic.BUTTONS: "buttons.state",
    StateTopic.DEVICES: "devices.state",
    StateTopic.HEALTH: "controller.health",
}

class LiveStatePublisher:
    """Retain bounded latest values while keeping the controller owner nonblocking."""

    def __init__(
        self,
        sio: socketio.AsyncServer,
        service: ControllerService,
        config: AppConfig,
    ) -> None:
        self._sio = sio
        self._service = service
        self._telemetry_interval_s = 1.0 / config.live_publication.telemetry_hz
        self._health_interval_s = 1.0 / config.live_publication.health_hz
        self._trace_interval_s = 1.0 / config.live_publication.trace_hz
        self._trace_batch_size = config.live_publication.trace_batch_size
        self._send_timeout_s = config.live_publication.send_timeout_s
        self._trace_capacity = config.simulation.trace_capacity
        self._resource_capacity = config.live_publication.resource_capacity
        self._shutdown_timeout_s = config.live_publication.shutdown_timeout_s
        self._lock = threading.Lock()
        self._pending_topics: dict[StateTopic, ControllerServiceSnapshot] = {}
        self._trace: deque[dict[str, object]] = deque(maxlen=self._trace_capacity)
        self._trace_session_id: int | None = None
        self._resources: deque[ResourceChangedEvent] = deque(maxlen=self._resource_capacity)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wake: asyncio.Event | None = None
        self._wake_scheduled = False
        self._task: asyncio.Task[None] | None = None
        self._stopping = False
        self._trace_subscribers: set[str] = set()
        self._trace_rows_dropped = 0
        self._resource_changes_dropped = 0
        self._failures = 0
        self._last_fault: str | None = None

    async def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("live-state publisher may be started exactly once")
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="live-state-publisher")
        self._sync_service_health()

    async def stop(self) -> None:
        self._stopping = True
        self._signal()
        task = self._task
        socket_shutdown = asyncio.create_task(
            self._sio.shutdown(),
            name="socketio-shutdown",
        )
        try:
            async with asyncio.timeout(self._shutdown_timeout_s):
                if task is not None:
                    await asyncio.gather(task, socket_shutdown)
                else:
                    await socket_shutdown
        except TimeoutError:
            LOGGER.warning(
                "live-state publisher shutdown exceeded %.3f seconds",
                self._shutdown_timeout_s,
            )
            with self._lock:
                self._failures += 1
                self._last_fault = "publisher shutdown deadline exceeded"
            if task is not None:
                task.cancel()
            socket_shutdown.cancel()
            await asyncio.gather(
                *(item for item in (task, socket_shutdown) if item is not None),
                return_exceptions=True,
            )
        finally:
            unfinished = tuple(
                item
                for item in (task, socket_shutdown)
                if item is not None and not item.done()
            )
            for item in unfinished:
                item.cancel()
            if unfinished:
                await asyncio.gather(*unfinished, return_exceptions=True)
            self._task = None
            self._loop = None
            self._wake = None
            self._trace_subscribers.clear()
            with self._lock:
                self._pending_topics.clear()
                self._trace.clear()
                self._resources.clear()
            self._sync_service_health(enqueue=False)

    def offer(self, execution: RuntimeExecution) -> None:
        """Accept one owner-thread notification without waiting on the ASGI loop."""

        snapshot = self._service.snapshot()
        with self._lock:
            session_id = snapshot.adapter.simulation_session_id
            if session_id != self._trace_session_id:
                self._trace.clear()
                self._trace_session_id = session_id
            for topic in execution.changed_topics:
                self._pending_topics[topic] = snapshot
            for trace_event in execution.events:
                if trace_event.get("type") == "frame":
                    if len(self._trace) == self._trace.maxlen:
                        self._trace_rows_dropped += 1
                    self._trace.append(trace_event)
        self._signal()
        self._sync_service_health()

    def offer_resource(self, event: ResourceChangedEvent) -> None:
        with self._lock:
            if len(self._resources) == self._resources.maxlen:
                self._resource_changes_dropped += 1
            self._resources.append(event)
        self._signal()
        self._sync_service_health()

    async def send_snapshot(self, sid: str) -> None:
        snapshot = self._service.snapshot()
        await self._emit(
            "controller.snapshot",
            self._envelope(snapshot, snapshot_data(snapshot)),
            to=sid,
        )

    async def subscribe_trace(self, sid: str) -> None:
        await self._sio.enter_room(sid, TRACE_ROOM)
        with self._lock:
            self._trace_subscribers.add(sid)

    async def unsubscribe_trace(self, sid: str) -> None:
        if sid in self._trace_subscribers:
            await self._sio.leave_room(sid, TRACE_ROOM)
            with self._lock:
                self._trace_subscribers.discard(sid)

    def disconnect(self, sid: str) -> None:
        with self._lock:
            self._trace_subscribers.discard(sid)
        self._sync_service_health()

    @property
    def diagnostics(self) -> PublisherDiagnostics:
        with self._lock:
            return PublisherDiagnostics(
                running=self.running,
                failures=self._failures,
                trace_rows_dropped=self._trace_rows_dropped,
                resource_changes_dropped=self._resource_changes_dropped,
                transport_queue_saturations=getattr(
                    getattr(self._sio, "eio", None),
                    "outbound_queue_saturations",
                    0,
                ),
                fault=self._last_fault,
            )

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

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
        next_trace = loop.time()
        next_health = loop.time()
        while True:
            now = loop.time()
            timeout = max(min(next_telemetry, next_trace, next_health) - now, 0.0)
            wake = self._wake
            assert wake is not None
            with suppress(TimeoutError):
                await asyncio.wait_for(wake.wait(), timeout=timeout)
            wake.clear()
            with self._lock:
                self._wake_scheduled = False

            now = loop.time()
            telemetry_due = now >= next_telemetry
            trace_due = now >= next_trace
            health_due = now >= next_health
            if self._stopping:
                await self._flush(telemetry_due=True, trace_due=True, health_due=True)
                return
            await self._flush(
                telemetry_due=telemetry_due,
                trace_due=trace_due,
                health_due=health_due,
            )
            if telemetry_due:
                next_telemetry = now + self._telemetry_interval_s
            if trace_due:
                next_trace = now + self._trace_interval_s
            if health_due:
                next_health = now + self._health_interval_s

    async def _flush(
        self,
        *,
        telemetry_due: bool,
        trace_due: bool,
        health_due: bool,
    ) -> None:
        with self._lock:
            selected_topics = {
                topic: snapshot
                for topic, snapshot in self._pending_topics.items()
                if (
                    (topic is StateTopic.HEALTH and health_due)
                    or (topic in TELEMETRY_TOPICS and telemetry_due)
                    or (topic not in TELEMETRY_TOPICS and topic is not StateTopic.HEALTH)
                )
            }
            for topic in selected_topics:
                self._pending_topics.pop(topic, None)
            resources = tuple(self._resources)
            self._resources.clear()
            trace_rows: tuple[dict[str, object], ...] = ()
            if trace_due:
                trace_rows = tuple(self._trace)[-self._trace_batch_size :]
                self._trace.clear()

        for topic, snapshot in selected_topics.items():
            await self._emit(
                TOPIC_EVENTS[topic],
                self._envelope(snapshot, _topic_data(topic, snapshot)),
            )
        for resource in resources:
            await self._emit("resources.changed", resource.model_dump())
        if trace_rows and self._trace_subscribers:
            snapshot = self._service.snapshot()
            batch = TraceBatchData(rows=tuple(TraceRow.model_validate(row) for row in trace_rows))
            await self._emit(
                "trace.batch",
                self._envelope(snapshot, batch),
                room=TRACE_ROOM,
            )

    async def _emit(
        self,
        event: str,
        payload: LiveEnvelope | dict[str, object],
        *,
        to: str | None = None,
        room: str | None = None,
    ) -> None:
        serialized = (
            payload.model_dump(mode="json")
            if isinstance(payload, LiveEnvelope)
            else payload
        )
        try:
            async with asyncio.timeout(self._send_timeout_s):
                await self._sio.emit(event, serialized, to=to, room=room)
        except Exception:
            LOGGER.warning("Socket.IO publication failed: event=%s", event, exc_info=True)
            with self._lock:
                self._failures += 1
                self._last_fault = f"Socket.IO publication failed: {event}"
            self._sync_service_health(enqueue=event != "controller.health")
            return
    def _sync_service_health(self, *, enqueue: bool = True) -> None:
        execution = self._service.update_publisher_health(self.diagnostics)
        if enqueue and execution is not None:
            self._enqueue_health(execution)

    def _enqueue_health(self, execution: RuntimeExecution) -> None:
        """Queue service-only health without feeding publisher diagnostics back recursively."""

        snapshot = self._service.snapshot()
        with self._lock:
            self._pending_topics[StateTopic.HEALTH] = snapshot
        self._signal()

    @staticmethod
    def _envelope(
        snapshot: ControllerServiceSnapshot,
        data: LiveData,
    ) -> LiveEnvelope:
        return LiveEnvelope(
            boot_id=snapshot.boot_id,
            revision=snapshot.revision,
            emitted_at=datetime.now(UTC),
            data=data,
        )


def install_socket_handlers(
    sio: socketio.AsyncServer,
    publisher: LiveStatePublisher,
) -> None:
    @sio.event  # type: ignore[untyped-decorator]
    async def connect(sid: str, environ: dict[str, Any], auth: object) -> None:
        del environ, auth
        await publisher.send_snapshot(sid)

    @sio.event  # type: ignore[untyped-decorator]
    async def disconnect(sid: str, reason: str) -> None:
        del reason
        publisher.disconnect(sid)

    @sio.on("controller.resync")  # type: ignore[untyped-decorator]
    async def resync(sid: str, payload: object = None) -> None:
        del payload
        await publisher.send_snapshot(sid)

    @sio.on("trace.subscribe")  # type: ignore[untyped-decorator]
    async def trace_subscribe(sid: str, payload: object = None) -> None:
        del payload
        await publisher.subscribe_trace(sid)

    @sio.on("trace.unsubscribe")  # type: ignore[untyped-decorator]
    async def trace_unsubscribe(sid: str, payload: object = None) -> None:
        del payload
        await publisher.unsubscribe_trace(sid)


def _topic_data(topic: StateTopic, snapshot: ControllerServiceSnapshot) -> LiveData:
    if topic is StateTopic.VEHICLE:
        return vehicle_state(snapshot)
    if topic is StateTopic.ENGINE:
        return engine_state(snapshot)
    if topic is StateTopic.STEERING:
        return steering_state(snapshot)
    if topic is StateTopic.BUTTONS:
        return buttons_state(snapshot)
    if topic is StateTopic.DEVICES:
        return devices_state(snapshot)
    if topic is StateTopic.HEALTH:
        return health_state(snapshot)
    raise AssertionError(f"unhandled state topic: {topic}")
