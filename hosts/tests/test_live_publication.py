from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from dataclasses import replace
from typing import Any, cast

import e87canbus.api.internal.coordinator_sse as coordinator_sse
import pytest
import socketio  # type: ignore[import-untyped]
from e87canbus.api.internal.coordinator_sse import CoordinatorSsePublisher
from e87canbus.api.internal.live import LiveStatePublisher
from e87canbus.api.models.resources import ResourceChangedEvent
from e87canbus.api.routes.live import EventStreamResponse
from e87canbus.config import LivePublicationConfig, simulator_config
from e87canbus.domain.intents import SetMaximumAssistance
from e87canbus.kernel import ExecuteOperatorIntent, StateTopic
from e87canbus.runners.composition import build_simulated_controller_loop
from e87canbus.runners.simulation.runtime import (
    ResetSimulation,
    SetVehicleSignal,
    TapButton,
)
from e87canbus.runners.simulation.signals import VehicleSignal
from e87canbus.service import ControllerLoop, ControllerLoopSnapshot, RuntimeExecution
from registry_test_support import activate_simulation_devices


class RecordingSocketServer:
    def __init__(self) -> None:
        self.emissions: list[tuple[str, dict[str, Any], str | None, str | None]] = []
        self.rooms: dict[str, set[str]] = {}
        self.block = False
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.shutdown_block = False
        self.shutdown_entered = asyncio.Event()
        self.shutdown_release = asyncio.Event()
        self.error: Exception | None = None

    async def emit(
        self,
        event: str,
        payload: dict[str, Any],
        *,
        to: str | None = None,
        room: str | None = None,
    ) -> None:
        if self.block:
            self.entered.set()
            await self.release.wait()
        if self.error is not None:
            raise self.error
        self.emissions.append((event, payload, to, room))

    async def enter_room(self, sid: str, room: str) -> None:
        self.rooms.setdefault(room, set()).add(sid)

    async def leave_room(self, sid: str, room: str) -> None:
        self.rooms.get(room, set()).discard(sid)

    async def shutdown(self) -> None:
        if self.shutdown_block:
            self.shutdown_entered.set()
            await self.shutdown_release.wait()


INITIAL_PUBLICATION_EVENTS = frozenset(
    {
        "engine.state",
        "steering.state",
        "vehicle.state",
        "devices.state",
        "lighting.state",
        "buttons.state",
        "controller.health",
    }
)


def controller_loop(
    *,
    trace_batch_size: int = 4,
    shutdown_timeout_s: float = 2.0,
    health_hz: float = 1.0,
) -> ControllerLoop:
    config = replace(
        simulator_config(),
        tick_interval_s=60.0,
        live_publication=LivePublicationConfig(
            telemetry_hz=25.0,
            health_hz=health_hz,
            trace_hz=100.0,
            trace_batch_size=trace_batch_size,
            resource_capacity=8,
            shutdown_timeout_s=shutdown_timeout_s,
        ),
    )
    return build_simulated_controller_loop(config=config)


def publisher_for(
    service: ControllerLoop,
    socket_server: RecordingSocketServer,
) -> LiveStatePublisher:
    return LiveStatePublisher(
        cast(socketio.AsyncServer, socket_server),
        service,
        service.config,
    )


async def wait_until(predicate: Callable[[], bool], timeout_s: float = 1.0) -> None:
    async def poll() -> None:
        while not predicate():
            await asyncio.sleep(0.005)

    await asyncio.wait_for(poll(), timeout=timeout_s)


async def wait_for_initial_publication(socket_server: RecordingSocketServer) -> None:
    await wait_until(
        lambda: {event for event, *_ in socket_server.emissions} >= INITIAL_PUBLICATION_EVENTS
    )


@pytest.mark.asyncio
async def test_snapshot_is_complete_and_new_boot_requires_replacement() -> None:
    first = controller_loop()
    second = controller_loop()
    first.start()
    second.start()
    first_socket = RecordingSocketServer()
    second_socket = RecordingSocketServer()
    first_publisher = publisher_for(first, first_socket)
    second_publisher = publisher_for(second, second_socket)
    await first_publisher.start()
    await second_publisher.start()
    try:
        await first_publisher.send_snapshot("first-client")
        await second_publisher.send_snapshot("second-client")
    finally:
        first.stop()
        second.stop()
        await first_publisher.stop()
        await second_publisher.stop()

    first_event, first_payload, first_to, _ = first_socket.emissions[0]
    _, second_payload, _, _ = second_socket.emissions[0]
    assert first_event == "controller.snapshot"
    assert first_to == "first-client"
    assert first_payload["protocol_version"] == 1
    assert first_payload["boot_id"] != second_payload["boot_id"]
    snapshot_revision = first_payload["revision"]
    assert snapshot_revision >= 2
    assert set(first_payload["data"]) == {
        "topic_revisions",
        "simulation_session_id",
        "vehicle",
        "engine",
        "steering",
        "buttons",
        "lighting",
        "devices",
        "health",
    }
    topic_revisions = first_payload["data"]["topic_revisions"]
    assert topic_revisions["health"] == snapshot_revision
    assert topic_revisions["vehicle"] == 1
    assert topic_revisions["engine"] == 1
    assert topic_revisions["steering"] >= 1
    assert 1 <= topic_revisions["buttons"] <= snapshot_revision
    assert topic_revisions["lighting"] == 1
    assert 2 <= topic_revisions["devices"] <= snapshot_revision
    assert first_payload["data"]["lighting"] == {
        "high_beam_enabled": False,
        "high_beam_strobe_active": False,
        "high_beam_strobe_cycles_remaining": 0,
        "observed_high_beam_enabled": False,
    }


@pytest.mark.asyncio
async def test_only_changed_topic_publishes_and_service_revision_survives_reset() -> None:
    service = controller_loop()
    socket_server = RecordingSocketServer()
    publisher = publisher_for(service, socket_server)
    await asyncio.to_thread(service.start, publisher.offer)
    await publisher.start()
    try:
        await wait_for_initial_publication(socket_server)
        socket_server.emissions.clear()
        assert all(entry.status.value == "active" for entry in service.snapshot().adapter.registry)
        result = await asyncio.wrap_future(
            service.submit(ExecuteOperatorIntent(SetMaximumAssistance(True)))
        )
        await wait_until(
            lambda: (
                {event for event, *_ in socket_server.emissions}
                >= {"steering.state", "buttons.state"}
            )
        )
        events = [event for event, *_ in socket_server.emissions]
        before_reset = service.snapshot()
        before_reset_revision = before_reset.revision
        command_topic_revision = dict(before_reset.topic_revisions)[StateTopic.STEERING]
        await asyncio.wrap_future(service.submit(ResetSimulation()))
        after_reset_revision = service.snapshot().revision
    finally:
        await asyncio.to_thread(service.stop)
        await publisher.stop()

    assert result == command_topic_revision
    assert result <= before_reset_revision
    assert set(events) == {"steering.state", "buttons.state"}
    assert after_reset_revision > before_reset_revision


@pytest.mark.asyncio
async def test_lighting_topic_publishes_requested_and_observed_high_beam_state() -> None:
    service = controller_loop()
    socket_server = RecordingSocketServer()
    publisher = publisher_for(service, socket_server)
    await asyncio.to_thread(service.start, publisher.offer)
    await publisher.start()
    try:
        await wait_for_initial_publication(socket_server)
        await asyncio.to_thread(activate_simulation_devices, service)
        socket_server.emissions.clear()
        await asyncio.wrap_future(service.submit(TapButton(4)))
        await wait_until(
            lambda: any(event == "lighting.state" for event, *_ in socket_server.emissions)
        )
    finally:
        await asyncio.to_thread(service.stop)
        await publisher.stop()

    payload = next(
        payload for event, payload, _, _ in socket_server.emissions if event == "lighting.state"
    )
    assert payload["data"] == {
        "high_beam_enabled": True,
        "high_beam_strobe_active": True,
        "high_beam_strobe_cycles_remaining": 5,
        "observed_high_beam_enabled": True,
    }


@pytest.mark.asyncio
async def test_persistence_only_change_advances_and_publishes_health_revision() -> None:
    service = controller_loop(health_hz=100.0)
    service.mark_persistence_available()
    socket_server = RecordingSocketServer()
    publisher = publisher_for(service, socket_server)
    await asyncio.to_thread(service.start, publisher.offer)
    await publisher.start()
    service.mark_ready()
    try:
        await wait_until(lambda: len(socket_server.emissions) >= 6)
        await publisher.send_snapshot("synchronized-client")
        synchronized_revision = socket_server.emissions[-1][1]["revision"]
        socket_server.emissions.clear()

        service.mark_persistence_fault("database unavailable")

        await wait_until(
            lambda: any(event == "controller.health" for event, *_ in socket_server.emissions)
        )
        event, payload, _, _ = socket_server.emissions[-1]
    finally:
        await asyncio.to_thread(service.stop)
        await publisher.stop()

    assert event == "controller.health"
    assert payload["revision"] > synchronized_revision
    assert payload["data"]["persistence"] == {
        "available": False,
        "fault": "database unavailable",
    }
    assert payload["data"]["ready"] is False


@pytest.mark.asyncio
async def test_publisher_failure_publishes_once_without_recursion() -> None:
    service = controller_loop(health_hz=100.0)
    service.mark_persistence_available()
    socket_server = RecordingSocketServer()
    publisher = publisher_for(service, socket_server)
    await asyncio.to_thread(service.start, publisher.offer)
    await publisher.start()
    service.mark_ready()
    try:
        await wait_until(lambda: len(socket_server.emissions) >= 6)
        socket_server.emissions.clear()
        socket_server.error = OSError("socket failed")
        before_failure_revision = service.snapshot().revision
        await publisher.send_snapshot("broken-client")
        socket_server.error = None

        await wait_until(
            lambda: any(event == "controller.health" for event, *_ in socket_server.emissions)
        )
        failure_payload = socket_server.emissions[-1][1]
        assert failure_payload["revision"] > before_failure_revision
        assert failure_payload["data"]["publisher"]["failures"] == 1
        await asyncio.sleep(0.04)
        assert [event for event, *_ in socket_server.emissions if event == "controller.health"] == [
            "controller.health"
        ]
    finally:
        await asyncio.to_thread(service.stop)
        await publisher.stop()


@pytest.mark.asyncio
async def test_stalled_emitter_retains_one_latest_value_per_topic() -> None:
    service = controller_loop()
    socket_server = RecordingSocketServer()
    publisher = publisher_for(service, socket_server)
    await asyncio.to_thread(service.start, publisher.offer)
    await publisher.start()
    await wait_until(lambda: len(socket_server.emissions) >= 6)
    socket_server.emissions.clear()
    socket_server.block = True
    execution = RuntimeExecution(
        changed_topics=frozenset({StateTopic.VEHICLE}),
        commit_count=1,
    )
    try:
        await asyncio.wait_for(
            asyncio.wrap_future(service.submit(SetVehicleSignal(VehicleSignal.SPEED, 42.0))),
            timeout=1.0,
        )
        await asyncio.wait_for(socket_server.entered.wait(), timeout=1.0)
        for _ in range(1_000):
            publisher.offer(execution)
        assert service.snapshot().application.vehicle_speed_kph == 42.0
        assert service.snapshot().diagnostics.health.fatal is False
    finally:
        socket_server.release.set()
        await asyncio.to_thread(service.stop)
        await publisher.stop()


def frame(sequence: int) -> dict[str, object]:
    return {
        "type": "frame",
        "session_id": 1,
        "sequence": sequence,
        "network": "kcan",
        "source": "test",
        "arbitration_id": 0x700,
        "arbitration_id_hex": "0x700",
        "data_hex": "0001",
        "is_extended_id": False,
        "monotonic_s": float(sequence),
    }


@pytest.mark.asyncio
async def test_trace_is_opt_in_batched_and_drops_old_rows() -> None:
    service = controller_loop(trace_batch_size=3)
    service.start()
    socket_server = RecordingSocketServer()
    publisher = publisher_for(service, socket_server)
    await publisher.start()
    execution = RuntimeExecution(
        events=tuple(frame(index) for index in range(1, 2_002)),
    )
    try:
        publisher.offer(execution)
        await asyncio.sleep(0.03)
        assert all(event != "trace.batch" for event, *_ in socket_server.emissions)
        await publisher.subscribe_trace("trace-client")
        publisher.offer(execution)
        await wait_until(
            lambda: any(event == "trace.batch" for event, *_ in socket_server.emissions)
        )
        trace_payload = next(
            payload for event, payload, _, _ in socket_server.emissions if event == "trace.batch"
        )
        await publisher.unsubscribe_trace("trace-client")
        prior_batches = sum(event == "trace.batch" for event, *_ in socket_server.emissions)
        publisher.offer(execution)
        await asyncio.sleep(0.03)
    finally:
        service.stop()
        await publisher.stop()

    assert [row["sequence"] for row in trace_payload["data"]["rows"]] == [1999, 2000, 2001]
    assert sum(event == "trace.batch" for event, *_ in socket_server.emissions) == prior_batches
    assert publisher.diagnostics.trace_rows_dropped == 3


@pytest.mark.asyncio
async def test_multiple_clients_receive_independent_current_snapshots() -> None:
    service = controller_loop()
    service.start()
    socket_server = RecordingSocketServer()
    publisher = publisher_for(service, socket_server)
    await publisher.start()
    try:
        await publisher.send_snapshot("client-a")
        await publisher.send_snapshot("client-b")
    finally:
        service.stop()
        await publisher.stop()

    snapshots = [item for item in socket_server.emissions if item[0] == "controller.snapshot"]
    assert [item[2] for item in snapshots] == ["client-a", "client-b"]
    first = {**snapshots[0][1], "emitted_at": None}
    second = {**snapshots[1][1], "emitted_at": None}
    assert first == second


@pytest.mark.asyncio
async def test_resource_change_is_exact_and_retention_is_bounded() -> None:
    service = controller_loop()
    service.start()
    socket_server = RecordingSocketServer()
    publisher = publisher_for(service, socket_server)
    await publisher.start()
    try:
        for revision in range(1, 10):
            publisher.offer_resource(
                ResourceChangedEvent(
                    resource="steering_profile",
                    id="profile-1",
                    revision=revision,
                )
            )
        await wait_until(
            lambda: any(event == "resources.changed" for event, *_ in socket_server.emissions)
        )
    finally:
        service.stop()
        await publisher.stop()

    payloads = [
        payload for event, payload, _, _ in socket_server.emissions if event == "resources.changed"
    ]
    assert len(payloads) == 8
    assert payloads[-1] == {
        "type": "resources.changed",
        "resource": "steering_profile",
        "id": "profile-1",
        "revision": 9,
    }
    assert publisher.diagnostics.resource_changes_dropped == 1


@pytest.mark.asyncio
async def test_socket_failure_is_transport_diagnostic_only() -> None:
    service = controller_loop()
    service.start()
    socket_server = RecordingSocketServer()
    socket_server.error = OSError("socket failed")
    publisher = publisher_for(service, socket_server)
    await publisher.start()
    try:
        await publisher.send_snapshot("broken-client")
        socket_server.error = None
    finally:
        service.stop()
        await publisher.stop()

    assert publisher.diagnostics.failures == 1
    assert service.snapshot().diagnostics.health.fatal is False


@pytest.mark.asyncio
async def test_stalled_shutdown_has_one_deadline_and_leaves_no_tasks() -> None:
    service = controller_loop(shutdown_timeout_s=0.05)
    service.start()
    socket_server = RecordingSocketServer()
    socket_server.block = True
    socket_server.shutdown_block = True
    publisher = publisher_for(service, socket_server)
    await publisher.start()
    publisher.offer_resource(
        ResourceChangedEvent(
            resource="steering_profile",
            id="stalled-peer",
            revision=1,
        )
    )
    await asyncio.wait_for(socket_server.entered.wait(), timeout=1.0)

    start = asyncio.get_running_loop().time()
    service.stop()
    await publisher.stop()
    elapsed = asyncio.get_running_loop().time() - start

    # The point of the test: the deadline is applied once, not per stalled peer. The
    # loop configures shutdown_timeout_s=0.05, so this ceiling is 5x the budget it
    # guards. Without it a regression hangs the suite instead of failing it.
    assert elapsed < 0.25
    assert publisher.running is False
    assert publisher.diagnostics.failures >= 1
    assert not {
        task.get_name() for task in asyncio.all_tasks() if task is not asyncio.current_task()
    } & {"live-state-publisher", "socketio-shutdown"}


def sse_publisher_for(
    service: ControllerLoop, *, client_queue_capacity: int = 64
) -> CoordinatorSsePublisher:
    config = replace(
        service.config,
        live_publication=replace(
            service.config.live_publication,
            client_queue_capacity=client_queue_capacity,
        ),
    )
    return CoordinatorSsePublisher(service, config)


def sse_data(record: str) -> dict[str, Any]:
    prefix = "data: "
    assert record.startswith(prefix)
    assert record.endswith("\n\n")
    return cast(dict[str, Any], json.loads(record.removeprefix(prefix)))


@pytest.mark.asyncio
async def test_sse_snapshot_is_first_and_contains_only_browser_projections() -> None:
    service = controller_loop()
    service.start()
    publisher = sse_publisher_for(service)
    await publisher.start()
    events = publisher.events()
    try:
        initial = sse_data(await anext(events))
    finally:
        await events.aclose()
        service.stop()
        await publisher.stop()

    assert initial["type"] == "snapshot"
    assert set(initial["data"]) == {
        "vehicle",
        "engine",
        "steering",
        "buttons",
        "lighting",
        "health",
    }
    assert "devices" not in initial["data"]
    assert "topic_revisions" not in initial["data"]
    assert "publisher" not in initial["data"]["health"]


@pytest.mark.asyncio
async def test_sse_projection_and_resource_events_are_complete_and_singular() -> None:
    service = controller_loop()
    service.start()
    publisher = sse_publisher_for(service)
    await publisher.start()
    events = publisher.events()
    try:
        await anext(events)
        await asyncio.wrap_future(
            service.submit(SetVehicleSignal(VehicleSignal.SPEED, 42.0))
        )
        publisher.offer(
            RuntimeExecution(changed_topics=frozenset({StateTopic.VEHICLE}), commit_count=1)
        )
        vehicle = sse_data(await asyncio.wait_for(anext(events), timeout=1.0))
        publisher.offer_resource(
            ResourceChangedEvent(resource="button_profile", id="profile-1", revision=3)
        )
        resource = sse_data(await asyncio.wait_for(anext(events), timeout=1.0))
    finally:
        await events.aclose()
        service.stop()
        await publisher.stop()

    assert vehicle == {
        "type": "vehicle",
        "data": {"speed_kph": 42.0, "speed_valid": True},
    }
    assert resource == {
        "type": "resource.changed",
        "data": {
            "resource": "button_profile",
            "id": "profile-1",
            "revision": 3,
        },
    }


@pytest.mark.asyncio
async def test_sse_registration_cannot_receive_a_drained_stale_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = controller_loop()
    service.start()
    publisher = sse_publisher_for(service)
    await publisher.start()
    await asyncio.sleep(0)
    original_topic_event = coordinator_sse._topic_event
    projection_drained = threading.Event()
    registration_attempted = threading.Event()
    release_projection = threading.Event()

    class RegistrationObservedLock:
        def __init__(self) -> None:
            self._lock = threading.Lock()

        def __enter__(self) -> None:
            if threading.current_thread().name == "sse-registration":
                registration_attempted.set()
            self._lock.acquire()

        def __exit__(
            self,
            exception_type: object,
            exception: object,
            traceback: object,
        ) -> None:
            del exception_type, exception, traceback
            self._lock.release()

    monkeypatch.setattr(publisher, "_lock", RegistrationObservedLock())

    def paused_topic_event(
        topic: StateTopic, snapshot: ControllerLoopSnapshot
    ) -> coordinator_sse.CoordinatorLiveEvent:
        projection_drained.set()
        assert release_projection.wait(timeout=1.0)
        return original_topic_event(topic, snapshot)

    monkeypatch.setattr(coordinator_sse, "_topic_event", paused_topic_event)
    errors: list[BaseException] = []
    subscribers: list[coordinator_sse._Subscriber] = []
    dummy_task = asyncio.create_task(asyncio.Event().wait())

    def register_during_drained_projection() -> None:
        try:
            assert projection_drained.wait(timeout=1.0)
            service.submit(SetVehicleSignal(VehicleSignal.SPEED, 42.0)).result(timeout=1.0)
            subscribers.append(publisher._register(dummy_task))
        except BaseException as error:
            errors.append(error)

    def release_after_registration_blocks() -> None:
        assert registration_attempted.wait(timeout=1.0)
        release_projection.set()

    worker = threading.Thread(
        target=register_during_drained_projection,
        name="sse-registration",
    )
    releaser = threading.Thread(target=release_after_registration_blocks)
    worker.start()
    releaser.start()
    try:
        publisher.offer(
            RuntimeExecution(changed_topics=frozenset({StateTopic.VEHICLE}), commit_count=1)
        )
        await asyncio.sleep(0.05)
        await asyncio.to_thread(worker.join, 1.0)
        await asyncio.to_thread(releaser.join, 1.0)
    finally:
        if subscribers:
            publisher._unregister(subscribers[0])
        dummy_task.cancel()
        await asyncio.gather(dummy_task, return_exceptions=True)
        service.stop()
        await publisher.stop()

    assert not worker.is_alive()
    assert not releaser.is_alive()
    assert errors == []
    assert len(subscribers) == 1
    pending = list(subscribers[0].pending)
    assert len(pending) == 1
    assert sse_data(pending[0])["data"]["vehicle"]["speed_kph"] == 42.0


@pytest.mark.asyncio
async def test_sse_saturation_cancels_a_request_blocked_in_asgi_send() -> None:
    service = controller_loop()
    service.start()
    publisher = sse_publisher_for(service, client_queue_capacity=2)
    await publisher.start()
    body_send_started = asyncio.Event()
    blocked_send = asyncio.Event()
    client_disconnected = asyncio.Event()

    async def receive() -> dict[str, object]:
        await client_disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, object]) -> None:
        if message["type"] == "http.response.body" and message.get("more_body") is True:
            body_send_started.set()
            await blocked_send.wait()

    async def serve() -> None:
        request_task = asyncio.current_task()
        assert request_task is not None
        response = EventStreamResponse(publisher.events(request_task))
        await response(
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
            },
            receive,
            send,
        )

    request_task = asyncio.create_task(serve())
    try:
        await asyncio.wait_for(body_send_started.wait(), timeout=1.0)
        for revision in range(1, 4):
            publisher.offer_resource(
                ResourceChangedEvent(
                    resource="steering_profile",
                    id="profile-1",
                    revision=revision,
                )
            )
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(request_task, timeout=1.0)
    finally:
        request_task.cancel()
        await asyncio.gather(request_task, return_exceptions=True)
        service.stop()
        await publisher.stop()

    assert publisher.slow_disconnects == 1
    assert publisher.subscriber_count == 0


@pytest.mark.asyncio
async def test_sse_shutdown_cancels_a_request_blocked_in_asgi_send() -> None:
    service = controller_loop(shutdown_timeout_s=0.05)
    service.start()
    publisher = sse_publisher_for(service)
    await publisher.start()
    response = EventStreamResponse(publisher.events())
    body_send_started = asyncio.Event()
    blocked_send = asyncio.Event()

    async def send(message: dict[str, object]) -> None:
        if message["type"] == "http.response.body" and message.get("more_body") is True:
            body_send_started.set()
            await blocked_send.wait()

    request_task = asyncio.create_task(response.stream_response(send))
    await asyncio.wait_for(body_send_started.wait(), timeout=1.0)
    start = asyncio.get_running_loop().time()
    await publisher.stop()
    elapsed = asyncio.get_running_loop().time() - start
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(request_task, timeout=1.0)
    service.stop()

    assert elapsed < 0.25
    assert publisher.running is False
    assert publisher.subscriber_count == 0


@pytest.mark.asyncio
async def test_sse_idle_comment_and_shutdown_release_subscriber(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(coordinator_sse, "KEEPALIVE_INTERVAL_S", 0.01)
    service = controller_loop()
    service.start()
    publisher = sse_publisher_for(service)
    await publisher.start()
    events = publisher.events()
    await anext(events)

    assert await asyncio.wait_for(anext(events), timeout=0.5) == ": keepalive\n\n"
    pending = asyncio.create_task(anext(events))
    await asyncio.sleep(0)
    await publisher.stop()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(pending, timeout=0.5)
    service.stop()

    assert publisher.running is False
    assert publisher.subscriber_count == 0
