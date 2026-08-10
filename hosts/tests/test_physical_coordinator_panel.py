from __future__ import annotations

import threading
import time
from collections.abc import Callable
from types import SimpleNamespace

import pytest
from e87canbus.adapters.coordinator_panel import UartPanelAdapter
from e87canbus.api.main import create_app
from e87canbus.deployment import DeploymentProfile
from e87canbus.hotspot import HotspotObservation
from e87canbus.runners.composition import build_controller_loop
from e87canbus.runners.coordinator_panel import PhysicalCoordinatorPanel
from e87canbus.service import ControllerLoopLifecycle


class FakeSerialPort:
    def __init__(self) -> None:
        self.incoming = bytearray()
        self.events: list[bytes | str] = []
        self.writes: list[tuple[float, bytes]] = []
        self.lock = threading.Lock()

    def read(self, size: int = 1) -> bytes:
        time.sleep(0.005)
        with self.lock:
            chunk = bytes(self.incoming[:size])
            del self.incoming[:size]
            return chunk

    def write(self, data: bytes) -> int:
        with self.lock:
            self.events.append(data)
            self.writes.append((time.monotonic(), data))
        return len(data)

    def close(self) -> None:
        with self.lock:
            self.events.append("closed")

    def button(self) -> None:
        with self.lock:
            self.incoming.extend(b"BUTTON\n")


class FakeHotspotBackend:
    def __init__(self) -> None:
        self.observation = HotspotObservation.DISABLED
        self.activation_calls = 0

    def activate(self) -> None:
        self.activation_calls += 1
        self.observation = HotspotObservation.STARTING

    def deactivate(self) -> None:
        self.observation = HotspotObservation.DISABLED

    def observe(self) -> HotspotObservation:
        return self.observation


class BlockingHotspotBackend(FakeHotspotBackend):
    """Hold the first observation, as a slow NetworkManager command does."""

    def __init__(self) -> None:
        super().__init__()
        self.observing = threading.Event()
        self.release = threading.Event()
        self._block_first_observation = True

    def observe(self) -> HotspotObservation:
        if self._block_first_observation:
            self._block_first_observation = False
            self.observing.set()
            assert self.release.wait(timeout=5.0)
        return super().observe()


class FakeController:
    def __init__(self) -> None:
        self.lifecycle = ControllerLoopLifecycle.CREATED
        self.ready = False
        self.snapshotted = threading.Event()

    def snapshot(self) -> SimpleNamespace:
        self.snapshotted.set()
        return SimpleNamespace(
            diagnostics=SimpleNamespace(health=SimpleNamespace(fatal=False)),
            service=SimpleNamespace(ready=self.ready),
        )


class FakeSocketCanBus:
    def __init__(self, interface: str) -> None:
        del interface

    def send(self, frame: object) -> None:
        del frame

    def receive(self, timeout_s: float | None = None) -> None:
        del timeout_s

    def shutdown(self) -> None:
        pass


def wait_for(
    predicate: Callable[[], bool],
    events: list[bytes | str] | None = None,
    timeout: float = 3.0,
) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, events
        time.sleep(0.01)


def test_pre_ready_button_is_not_retained_while_hotspot_observation_is_blocked() -> None:
    controller = FakeController()
    controller.lifecycle = ControllerLoopLifecycle.RUNNING
    port = FakeSerialPort()
    backend = BlockingHotspotBackend()
    accessory = PhysicalCoordinatorPanel(
        controller,  # type: ignore[arg-type]
        uart_factory=lambda: UartPanelAdapter(port),
        hotspot_backend=backend,
    )

    accessory.start()
    assert backend.observing.wait(timeout=0.5)
    # The state worker is held inside its observation, so the next snapshot is the UART
    # thread capturing the coordinator status of this press.
    controller.snapshotted.clear()
    port.button()
    assert controller.snapshotted.wait(timeout=0.5)
    controller.ready = True
    backend.release.set()
    try:
        wait_for(lambda: b"STATUS ready\n" in port.events, port.events)
        assert backend.activation_calls == 0
        port.button()
        wait_for(lambda: backend.activation_calls == 1)
    finally:
        accessory.stop()

    assert port.events[-2:] == [b"STATUS off\n", "closed"]


def test_ready_button_remains_valid_while_hotspot_observation_is_blocked() -> None:
    controller = FakeController()
    controller.lifecycle = ControllerLoopLifecycle.RUNNING
    controller.ready = True
    port = FakeSerialPort()
    backend = BlockingHotspotBackend()
    accessory = PhysicalCoordinatorPanel(
        controller,  # type: ignore[arg-type]
        uart_factory=lambda: UartPanelAdapter(port),
        hotspot_backend=backend,
    )

    accessory.start()
    assert backend.observing.wait(timeout=0.5)
    # The state worker is held inside its observation, so the next snapshot is the UART
    # thread capturing the coordinator status of this press.
    controller.snapshotted.clear()
    port.button()
    assert controller.snapshotted.wait(timeout=0.5)
    controller.ready = False
    backend.release.set()
    try:
        wait_for(lambda: backend.activation_calls == 1)
    finally:
        accessory.stop()

    assert port.events[-2:] == [b"STATUS off\n", "closed"]


def test_blocked_hotspot_observation_does_not_stop_the_uart_heartbeat() -> None:
    controller = FakeController()
    port = FakeSerialPort()
    backend = BlockingHotspotBackend()
    accessory = PhysicalCoordinatorPanel(
        controller,  # type: ignore[arg-type]
        uart_factory=lambda: UartPanelAdapter(port),
        hotspot_backend=backend,
    )

    accessory.start()
    assert backend.observing.wait(timeout=0.5)
    try:
        # The state worker is held inside its observation, so these heartbeats can only
        # come from the independent UART loop.
        wait_for(lambda: len(port.writes) >= 2, port.events, timeout=3.0)
    finally:
        backend.release.set()
        accessory.stop()

    assert port.events[-2:] == [b"STATUS off\n", "closed"]


@pytest.mark.parametrize(
    ("profile", "physical"),
    [
        (DeploymentProfile.CAR, True),
        (DeploymentProfile.BENCH, True),
        (DeploymentProfile.SIMULATOR, False),
    ],
)
def test_application_composes_physical_panel_only_for_physical_profiles(
    profile: DeploymentProfile,
    physical: bool,
    tmp_path,
) -> None:
    service = build_controller_loop(
        profile,
        socketcan_factory=FakeSocketCanBus,
        profile_database_path=tmp_path / f"{profile.value}.sqlite3",
    )
    app = create_app(controller_loop=service, profile_database_path=tmp_path / "api.sqlite3")

    assert isinstance(app.state.coordinator_panel, PhysicalCoordinatorPanel) is physical
