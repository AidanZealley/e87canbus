from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import replace
from queue import Empty, Queue
from typing import Any, cast

import e87canbus.console.sse as console_sse
import pytest
from e87canbus.console.app import EventStreamResponse
from e87canbus.console.service import ConsoleCanService
from e87canbus.console.sse import ConsoleSsePublisher
from e87canbus.protocol.can import CanFrame


class FakeReceiver:
    def __init__(self) -> None:
        self.items: Queue[CanFrame | Exception] = Queue()

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        try:
            item = self.items.get(timeout=timeout_s)
        except Empty:
            return None
        if isinstance(item, Exception):
            raise item
        return item

    def shutdown(self) -> None:
        pass


def sse_data(record: str) -> dict[str, Any]:
    assert record.startswith("data: ")
    assert record.endswith("\n\n")
    return cast(dict[str, Any], json.loads(record.removeprefix("data: ")))


async def wait_until(predicate, timeout_s: float = 1.0) -> None:
    async def poll() -> None:
        while not predicate():
            await asyncio.sleep(0.002)

    await asyncio.wait_for(poll(), timeout=timeout_s)


@pytest.mark.asyncio
async def test_snapshot_is_first_and_activity_is_complete_latest_state() -> None:
    receiver = FakeReceiver()
    service = ConsoleCanService(lambda: receiver)
    publisher = ConsoleSsePublisher(service, publication_interval_s=0.02)
    await publisher.start()
    service.start(publisher.offer)
    events = publisher.events()
    try:
        initial = sse_data(await anext(events))
        for index in range(100):
            receiver.items.put(CanFrame(index, bytes([index % 256])))
        await wait_until(lambda: service.snapshot().frames_received == 100)
        changed = sse_data(await asyncio.wait_for(anext(events), timeout=1.0))
    finally:
        await events.aclose()
        service.stop()
        await publisher.stop()

    assert initial == {
        "type": "console.snapshot",
        "data": {
            "can": {
                "interface": "kcan",
                "connected": True,
                "frames_received": 0,
                "fault": None,
            }
        },
    }
    assert changed["data"]["can"]["frames_received"] == 100
    assert "boot_id" not in changed
    assert "revision" not in changed


@pytest.mark.asyncio
async def test_concurrent_registration_cannot_queue_an_older_snapshot() -> None:
    receiver = FakeReceiver()
    service = ConsoleCanService(lambda: receiver)
    publisher = ConsoleSsePublisher(service, publication_interval_s=60.0)
    await publisher.start()
    service.start(lambda _snapshot: None)
    older = service.snapshot()
    receiver.items.put(CanFrame(1, b"one"))
    receiver.items.put(CanFrame(2, b"two"))
    await wait_until(lambda: service.snapshot().frames_received == 2)

    with publisher._lock:
        publisher._pending_snapshot = older
    barrier = threading.Barrier(2)
    dummy_task = asyncio.create_task(asyncio.Event().wait())
    subscribers: list[console_sse._Subscriber] = []

    def register() -> None:
        barrier.wait()
        subscribers.append(publisher._register(dummy_task))

    def publish_older_snapshot() -> None:
        barrier.wait()
        publisher._flush()

    registration = threading.Thread(target=register)
    publication = threading.Thread(target=publish_older_snapshot)
    registration.start()
    publication.start()
    await asyncio.to_thread(registration.join, 1.0)
    await asyncio.to_thread(publication.join, 1.0)
    try:
        assert not registration.is_alive()
        assert not publication.is_alive()
        assert len(subscribers) == 1
        subscriber = subscribers[0]
        assert len(subscriber.pending) == 1
        assert sse_data(subscriber.pending[0])["data"]["can"]["frames_received"] == 2
    finally:
        if subscribers:
            publisher._unregister(subscribers[0])
        dummy_task.cancel()
        await asyncio.gather(dummy_task, return_exceptions=True)
        service.stop()
        await publisher.stop()


@pytest.mark.asyncio
async def test_fault_bypasses_activity_cadence() -> None:
    receiver = FakeReceiver()
    service = ConsoleCanService(lambda: receiver)
    publisher = ConsoleSsePublisher(service, publication_interval_s=60.0)
    await publisher.start()
    service.start(publisher.offer)
    events = publisher.events()
    try:
        await anext(events)
        receiver.items.put(OSError("reader stopped"))
        fault = sse_data(await asyncio.wait_for(anext(events), timeout=1.0))
    finally:
        await events.aclose()
        service.stop()
        await publisher.stop()

    assert fault["data"]["can"]["fault"] == "kcan receive failed: reader stopped"


@pytest.mark.asyncio
async def test_saturation_cancels_a_request_blocked_in_asgi_send() -> None:
    service = ConsoleCanService(lambda: FakeReceiver())
    publisher = ConsoleSsePublisher(
        service,
        publication_interval_s=0.0,
        client_capacity=2,
    )
    await publisher.start()
    service.start(lambda _snapshot: None)
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
        snapshot = service.snapshot()
        for revision in range(snapshot.revision + 1, snapshot.revision + 4):
            publisher.offer(replace(snapshot, revision=revision, frames_received=revision))
            await asyncio.sleep(0.01)
        await wait_until(lambda: publisher.slow_disconnects == 1)
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
async def test_idle_comment_and_shutdown_release_subscriber(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(console_sse, "KEEPALIVE_INTERVAL_S", 0.01)
    service = ConsoleCanService(lambda: FakeReceiver())
    publisher = ConsoleSsePublisher(service, shutdown_timeout_s=0.05)
    await publisher.start()
    service.start(lambda _snapshot: None)
    events = publisher.events()
    await anext(events)

    assert await asyncio.wait_for(anext(events), timeout=0.5) == ": keepalive\n\n"
    pending = asyncio.create_task(anext(events))
    await asyncio.sleep(0)
    start = asyncio.get_running_loop().time()
    await publisher.stop()
    elapsed = asyncio.get_running_loop().time() - start
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(pending, timeout=0.5)
    service.stop()

    assert elapsed < 0.25
    assert publisher.running is False
    assert publisher.subscriber_count == 0
