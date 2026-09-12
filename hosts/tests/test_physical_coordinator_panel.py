from __future__ import annotations

import threading
import time
from collections.abc import Callable
from types import SimpleNamespace

import pytest
from e87canbus.adapters.coordinator_panel import UartPanelAdapter
from e87canbus.api.main import create_app
from e87canbus.deployment import DeploymentProfile
from e87canbus.runners.composition import build_controller_loop
from e87canbus.runners.coordinator_panel import PhysicalCoordinatorPanel
from e87canbus.service import ControllerLoopLifecycle


class FakeSerialPort:
    def __init__(self) -> None:
        self.events: list[bytes | str] = []
        self.lock = threading.Lock()
        self.fail_writes = False

    def write(self, data: bytes) -> int:
        with self.lock:
            if self.fail_writes:
                raise OSError("simulated UART write failure")
            self.events.append(data)
        return len(data)

    def close(self) -> None:
        with self.lock:
            self.events.append("closed")


class FakeController:
    def __init__(self) -> None:
        self.lifecycle = ControllerLoopLifecycle.CREATED
        self.ready = False
        self.fatal = False

    def snapshot(self) -> SimpleNamespace:
        return SimpleNamespace(
            diagnostics=SimpleNamespace(health=SimpleNamespace(fatal=self.fatal)),
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
    events: list[bytes | str],
    timeout: float = 3.0,
) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, events
        time.sleep(0.01)


def test_panel_heartbeats_status_and_sends_off_on_graceful_stop() -> None:
    controller = FakeController()
    port = FakeSerialPort()
    accessory = PhysicalCoordinatorPanel(
        controller,  # type: ignore[arg-type]
        uart_factory=lambda: UartPanelAdapter(port),
    )

    accessory.start()
    wait_for(lambda: b"STATUS starting\n" in port.events, port.events)
    controller.lifecycle = ControllerLoopLifecycle.RUNNING
    controller.ready = True
    wait_for(lambda: b"STATUS ready\n" in port.events, port.events)
    controller.fatal = True
    wait_for(lambda: b"STATUS fault\n" in port.events, port.events)
    accessory.stop()

    assert port.events[-2:] == [b"STATUS off\n", "closed"]


def test_uart_write_failure_stops_heartbeats_without_sending_graceful_off() -> None:
    controller = FakeController()
    port = FakeSerialPort()
    accessory = PhysicalCoordinatorPanel(
        controller,  # type: ignore[arg-type]
        uart_factory=lambda: UartPanelAdapter(port),
    )

    accessory.start()
    wait_for(lambda: b"STATUS starting\n" in port.events, port.events)
    port.fail_writes = True
    wait_for(lambda: "closed" in port.events, port.events)
    accessory.stop()

    assert b"STATUS off\n" not in port.events


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
