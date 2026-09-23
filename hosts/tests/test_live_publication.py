from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import replace
from typing import Any, cast

import e87canbus.api.internal.coordinator_sse as coordinator_sse
import pytest
from e87canbus.api.internal.coordinator_sse import CoordinatorSsePublisher
from e87canbus.api.models.resources import ResourceChangedEvent
from e87canbus.api.routes.live import EventStreamResponse
from e87canbus.config import simulator_config
from e87canbus.kernel import StateTopic
from e87canbus.runners.composition import build_simulated_controller_loop
from e87canbus.runners.simulation.runtime import SetVehicleSignal
from e87canbus.runners.simulation.signals import VehicleSignal
from e87canbus.service import ControllerLoop, ControllerLoopSnapshot, RuntimeExecution


def controller_loop(*, shutdown_timeout_s: float = 2.0) -> ControllerLoop:
    config = simulator_config()
    return build_simulated_controller_loop(
        config=replace(
            config,
            tick_interval_s=60.0,
            live_publication=replace(
                config.live_publication,
                shutdown_timeout_s=shutdown_timeout_s,
            ),
        )
    )


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
        await asyncio.wrap_future(service.submit(SetVehicleSignal(VehicleSignal.SPEED, 42.0)))
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
