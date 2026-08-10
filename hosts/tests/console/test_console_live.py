from __future__ import annotations

import asyncio
from queue import Empty, Queue
from typing import Any, cast

import pytest
import socketio  # type: ignore[import-untyped]
from e87canbus.console.live import ConsoleLivePublisher
from e87canbus.console.service import ConsoleCanService
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


class RecordingSocketServer:
    def __init__(self) -> None:
        self.emissions: list[tuple[str, dict[str, Any], str | None]] = []
        self.shutdown_called = False

    async def emit(self, event: str, payload: dict[str, Any], *, to: str | None = None) -> None:
        self.emissions.append((event, payload, to))

    async def shutdown(self) -> None:
        self.shutdown_called = True


async def wait_until(predicate, timeout_s: float = 1.0) -> None:
    async def poll() -> None:
        while not predicate():
            await asyncio.sleep(0.002)

    await asyncio.wait_for(poll(), timeout=timeout_s)


@pytest.mark.asyncio
async def test_activity_is_latest_state_coalesced_and_snapshot_contains_no_raw_can() -> None:
    receiver = FakeReceiver()
    service = ConsoleCanService(lambda: receiver)
    socket_server = RecordingSocketServer()
    publisher = ConsoleLivePublisher(
        cast(socketio.AsyncServer, socket_server),
        service,
        publication_interval_s=0.05,
    )
    await publisher.start()
    service.start(publisher.offer)
    await wait_until(lambda: len(socket_server.emissions) == 1)

    for index in range(100):
        receiver.items.put(CanFrame(index, bytes([index % 256])))
    await wait_until(lambda: service.snapshot().frames_received == 100)
    await wait_until(lambda: len(socket_server.emissions) == 2)
    await asyncio.sleep(0.02)
    service.stop()
    await publisher.stop()

    assert len(socket_server.emissions) == 2
    event, payload, _ = socket_server.emissions[-1]
    assert event == "console.snapshot"
    assert set(payload) == {"protocol_version", "boot_id", "revision", "emitted_at", "data"}
    assert payload["data"] == {
        "can": {
            "interface": "kcan",
            "connected": True,
            "frames_received": 100,
            "fault": None,
        }
    }
    assert "arbitration" not in repr(payload)
    assert "payload" not in repr(payload)


@pytest.mark.asyncio
async def test_fault_publication_is_prompt_and_connection_snapshot_is_complete() -> None:
    receiver = FakeReceiver()
    service = ConsoleCanService(lambda: receiver)
    socket_server = RecordingSocketServer()
    publisher = ConsoleLivePublisher(
        cast(socketio.AsyncServer, socket_server),
        service,
        publication_interval_s=60.0,
    )
    await publisher.start()
    service.start(publisher.offer)
    await wait_until(lambda: len(socket_server.emissions) == 1)
    await publisher.send_snapshot("new-client")
    receiver.items.put(OSError("reader stopped"))
    await wait_until(lambda: len(socket_server.emissions) == 3)
    service.stop()
    await publisher.stop()

    _, connection_payload, to = socket_server.emissions[1]
    assert to == "new-client"
    assert connection_payload["data"]["can"]["connected"] is True
    _, fault_payload, _ = socket_server.emissions[2]
    assert fault_payload["data"]["can"] == {
        "interface": "kcan",
        "connected": False,
        "frames_received": 0,
        "fault": "kcan receive failed: reader stopped",
    }
