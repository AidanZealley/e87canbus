from __future__ import annotations

import json
import time
from queue import Empty, Queue

from e87canbus.console.app import CONSOLE_SOCKET_PATH, create_app
from e87canbus.protocol.can import CanFrame
from fastapi.testclient import TestClient


class FakeReceiver:
    def __init__(self) -> None:
        self.frames: Queue[CanFrame] = Queue()
        self.closed = False

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        try:
            return self.frames.get(timeout=timeout_s)
        except Empty:
            return None

    def shutdown(self) -> None:
        self.closed = True


def test_fake_frame_reaches_socketio_as_a_complete_bounded_snapshot() -> None:
    receiver = FakeReceiver()
    app = create_app(receiver_factory=lambda: receiver)
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "live"}
        assert client.get("/health/ready").status_code == 200
        handshake = client.get(f"{CONSOLE_SOCKET_PATH}/?EIO=4&transport=polling")
        sid = json.loads(handshake.text[1:])["sid"]
        session_path = f"{CONSOLE_SOCKET_PATH}/?EIO=4&transport=polling&sid={sid}"
        assert client.post(session_path, content="40").status_code == 200
        initial_packets = client.get(session_path).text.split("\x1e")
        initial = next(packet for packet in initial_packets if packet.startswith("42"))
        event, payload = json.loads(initial[2:])
        assert event == "console.snapshot"
        assert payload["data"]["can"] == {
            "interface": "kcan",
            "connected": True,
            "frames_received": 0,
            "fault": None,
        }

        receiver.frames.put(CanFrame(0x777, b"must not escape"))
        deadline = time.monotonic() + 1.0
        while app.state.console_service.snapshot().frames_received != 1:
            assert time.monotonic() < deadline
            time.sleep(0.005)
        changed_packets = client.get(session_path).text.split("\x1e")
        changed = next(packet for packet in changed_packets if packet.startswith("42"))
        event, payload = json.loads(changed[2:])

        assert event == "console.snapshot"
        assert payload["data"]["can"]["frames_received"] == 1
        assert set(payload["data"]["can"]) == {
            "interface",
            "connected",
            "frames_received",
            "fault",
        }
    assert receiver.closed is True


def test_open_failure_keeps_liveness_available_and_readiness_false() -> None:
    def fail_open() -> FakeReceiver:
        raise OSError("kcan missing")

    app = create_app(receiver_factory=fail_open)
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
