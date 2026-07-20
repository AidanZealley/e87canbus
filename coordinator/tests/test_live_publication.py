from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from typing import Any, cast

import pytest
import socketio  # type: ignore[import-untyped]
from e87canbus.api.internal.live import LiveStatePublisher
from e87canbus.api.models.resources import ResourceChangedEvent
from e87canbus.composition import build_simulated_controller_service
from e87canbus.config import LivePublicationConfig, simulator_config
from e87canbus.runtime import SetMaximumAssistance, StateTopic
from e87canbus.service import ControllerService, RuntimeExecution
from e87canbus.simulation.runtime import (
    ResetSimulation,
    SetVehicleSignal,
    TapButton,
)
from e87canbus.simulation.signals import VehicleSignal
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


def controller_service(
    *,
    trace_batch_size: int = 4,
    shutdown_timeout_s: float = 2.0,
    health_hz: float = 1.0,
) -> ControllerService:
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
    return build_simulated_controller_service(config=config)


def publisher_for(
    service: ControllerService,
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
    first = controller_service()
    second = controller_service()
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
    assert topic_revisions["buttons"] == 1
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
    service = controller_service()
    socket_server = RecordingSocketServer()
    publisher = publisher_for(service, socket_server)
    await asyncio.to_thread(service.start, publisher.offer)
    await publisher.start()
    try:
        await wait_for_initial_publication(socket_server)
        socket_server.emissions.clear()
        assert all(entry.status.value == "active" for entry in service.snapshot().adapter.registry)
        result = await asyncio.wrap_future(service.submit(SetMaximumAssistance(True)))
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
    service = controller_service()
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
    service = controller_service(health_hz=100.0)
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
    service = controller_service(health_hz=100.0)
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
    service = controller_service()
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
        controller_result = await asyncio.wait_for(
            asyncio.wrap_future(service.submit(SetVehicleSignal(VehicleSignal.SPEED, 42.0))),
            timeout=1.0,
        )
        await asyncio.wait_for(socket_server.entered.wait(), timeout=1.0)
        for _ in range(1_000):
            publisher.offer(execution)
        assert type(controller_result) is int
        assert service.snapshot().application.vehicle_speed_kph == 42.0
        assert len(publisher._pending_topics) <= 2
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
    service = controller_service(trace_batch_size=3)
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
    service = controller_service()
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
    service = controller_service()
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
    service = controller_service()
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
    service = controller_service(shutdown_timeout_s=0.05)
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

    assert elapsed < 0.25
    assert publisher.running is False
    assert publisher.diagnostics.failures >= 1
    assert not {
        task.get_name() for task in asyncio.all_tasks() if task is not asyncio.current_task()
    } & {"live-state-publisher", "socketio-shutdown"}
