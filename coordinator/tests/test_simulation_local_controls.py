from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from e87canbus.api.errors import ApiProblem
from e87canbus.api.main import create_app
from e87canbus.config import simulator_config
from e87canbus.deployment import DeploymentProfile, deployment_spec
from e87canbus.domain.buttons.repository import ButtonProfileRepository
from e87canbus.domain.settings.repository import ApplicationSettingsRepository
from e87canbus.domain.steering.repository import SteeringProfileRepository
from e87canbus.local_controls import (
    CoordinatorCondition,
    CoordinatorConditionChanged,
    HotspotLifecycle,
    HotspotObserved,
    LocalControlsEvent,
    LocalControlsLifecycle,
    LocalControlsState,
    PanelButtonPressed,
    PanelDisplayState,
    PanelLink,
    PanelLinkChanged,
)
from e87canbus.runners.composition import ControllerConditionAdapter, controller_condition
from e87canbus.runners.simulation.api.internal import commands as simulation_commands
from e87canbus.runners.simulation.commands import ResetSimulation
from e87canbus.runners.simulation.local_controls import InMemoryHotspot, InMemoryPanel
from e87canbus.runners.simulation.runtime import SimulatedControllerRuntime
from e87canbus.service import (
    ControllerLoop,
    ControllerLoopError,
    ControllerLoopLifecycle,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient


def wait_for_state(
    client: TestClient,
    predicate: Callable[[LocalControlsState], bool],
    timeout_s: float = 1.0,
) -> None:
    deadline = time.monotonic() + timeout_s
    service = cast(FastAPI, client.app).state.local_controls_service
    while not predicate(service.snapshot().state):
        assert time.monotonic() < deadline
        time.sleep(0.01)


def test_simulator_causes_drive_every_hotspot_and_panel_observation(tmp_path: Path) -> None:
    app = create_app(
        profile=DeploymentProfile.SIMULATOR,
        profile_database_path=tmp_path / "simulator.sqlite3",
    )
    with TestClient(app) as client:
        service = app.state.local_controls_service
        wait_for_state(client, lambda state: state.coordinator is CoordinatorCondition.READY)

        assert client.post("/api/dev/simulation/coordinator-panel/button/tap").status_code == 200
        wait_for_state(client, lambda state: state.hotspot is HotspotLifecycle.ACTIVATING)
        activating = service.snapshot().state
        assert activating.hotspot is HotspotLifecycle.ACTIVATING
        assert activating.desired_display is PanelDisplayState.HOTSPOT_WAITING

        wait_for_state(client, lambda state: state.hotspot is HotspotLifecycle.ACTIVE)
        assert client.put(
            "/api/dev/simulation/coordinator-panel/client", json={"connected": True}
        ).status_code == 200
        wait_for_state(client, lambda state: state.client_connected)
        assert service.snapshot().state.desired_display is PanelDisplayState.HOTSPOT_CONNECTED

        assert client.put(
            "/api/dev/simulation/coordinator-panel/link", json={"connected": False}
        ).status_code == 200
        wait_for_state(client, lambda state: state.panel_link is PanelLink.DISCONNECTED)
        disconnected = service.snapshot().state
        assert disconnected.desired_display is PanelDisplayState.HOTSPOT_CONNECTED
        assert disconnected.effective_display is PanelDisplayState.FAULT

        assert client.put(
            "/api/dev/simulation/coordinator-panel/link", json={"connected": True}
        ).status_code == 200
        assert client.post("/api/dev/simulation/coordinator-panel/button/tap").status_code == 200
        wait_for_state(client, lambda state: state.hotspot is HotspotLifecycle.DEACTIVATING)
        wait_for_state(client, lambda state: state.hotspot is HotspotLifecycle.DISABLED)
        assert service.snapshot().state.desired_display is PanelDisplayState.READY

        assert client.put(
            "/api/dev/simulation/coordinator-panel/hotspot-failure",
            json={"enabled": True},
        ).status_code == 200
        wait_for_state(client, lambda state: state.hotspot is HotspotLifecycle.FAULT)
        assert service.snapshot().state.desired_display is PanelDisplayState.FAULT
        assert client.get("/health/ready").status_code == 200
        assert app.state.controller_loop.ready is True
        assert client.put(
            "/api/dev/simulation/coordinator-panel/hotspot-failure",
            json={"enabled": False},
        ).status_code == 200
        wait_for_state(client, lambda state: state.hotspot is HotspotLifecycle.DISABLED)
        assert service.snapshot().state.desired_display is PanelDisplayState.READY


def test_hotspot_transition_deadlines_use_the_simulator_clock() -> None:
    now = 10.0
    observed = []
    hotspot = InMemoryHotspot(clock=lambda: now, transition_s=0.25)
    hotspot.start(lambda event: observed.append(event) is None)

    hotspot.activate()
    hotspot.poll(10.24)
    assert observed == []
    hotspot.poll(10.25)
    assert observed == [HotspotObserved(HotspotLifecycle.ACTIVE)]

    now = 20.0
    hotspot.deactivate()
    hotspot.poll(20.25)
    assert observed[-1] == HotspotObserved(HotspotLifecycle.DISABLED)


class RejectOnceSink:
    def __init__(self) -> None:
        self.calls: list[LocalControlsEvent] = []
        self.accepted: list[LocalControlsEvent] = []
        self._reject = True

    def __call__(self, event: LocalControlsEvent) -> bool:
        self.calls.append(event)
        if self._reject:
            self._reject = False
            return False
        self.accepted.append(event)
        return True


def test_condition_adapter_retries_an_observation_rejected_by_the_inbox() -> None:
    controller = ControllerLoop(
        SimulatedControllerRuntime(config=simulator_config()),
        deployment=deployment_spec(DeploymentProfile.SIMULATOR),
    )
    condition = ControllerConditionAdapter(controller)
    sink = RejectOnceSink()

    condition.start(sink)
    condition.poll(time.monotonic())
    condition.poll(time.monotonic())

    expected = CoordinatorConditionChanged(CoordinatorCondition.STARTING)
    assert sink.calls == [expected, expected]
    assert sink.accepted == [expected]


def test_panel_link_commits_only_after_the_observation_is_accepted() -> None:
    panel = InMemoryPanel()
    sink = RejectOnceSink()
    panel.start(sink)

    assert panel.set_link(PanelLink.DISCONNECTED) is False
    assert panel.effective_display is PanelDisplayState.STARTING
    assert panel.set_link(PanelLink.DISCONNECTED) is True

    expected = PanelLinkChanged(PanelLink.DISCONNECTED)
    assert sink.calls == [expected, expected]
    assert sink.accepted == [expected]
    assert panel.effective_display is PanelDisplayState.FAULT


def test_panel_button_retry_does_not_consume_a_rejected_sequence() -> None:
    panel = InMemoryPanel()
    sink = RejectOnceSink()
    panel.start(sink)

    assert panel.tap_button() is False
    assert panel.tap_button() is True

    expected = PanelButtonPressed(sequence=1)
    assert sink.calls == [expected, expected]
    assert sink.accepted == [expected]


def test_hotspot_deadline_retries_until_transition_observation_is_accepted() -> None:
    hotspot = InMemoryHotspot(clock=lambda: 1.0, transition_s=0.25)
    sink = RejectOnceSink()
    hotspot.start(sink)
    hotspot.activate()

    hotspot.poll(1.25)
    assert hotspot.set_client_connected(True) is False
    hotspot.poll(1.25)
    assert hotspot.set_client_connected(True) is True

    transitioned = HotspotObserved(HotspotLifecycle.ACTIVE)
    client = HotspotObserved(HotspotLifecycle.ACTIVE, True)
    assert sink.calls[:2] == [transitioned, transitioned]
    assert sink.accepted == [transitioned, client]


def test_hotspot_client_and_failure_causes_retry_without_hidden_state() -> None:
    hotspot = InMemoryHotspot(clock=lambda: 1.0, transition_s=0.0)
    hotspot.start(lambda _event: True)
    hotspot.activate()
    hotspot.poll(1.0)

    client_sink = RejectOnceSink()
    hotspot.start(client_sink)
    assert hotspot.set_client_connected(True) is False
    assert hotspot.set_client_connected(True) is True
    assert client_sink.accepted == [HotspotObserved(HotspotLifecycle.ACTIVE, True)]

    failure_sink = RejectOnceSink()
    hotspot.start(failure_sink)
    assert hotspot.set_failure(True) is False
    hotspot.activate()  # A rejected failure injection did not secretly enable failure.
    assert hotspot.set_failure(True) is True
    with pytest.raises(OSError, match="simulated hotspot adapter failure"):
        hotspot.activate()


def test_reset_clears_local_causes_and_exposes_startup_before_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(
        profile=DeploymentProfile.SIMULATOR,
        profile_database_path=tmp_path / "simulator.sqlite3",
    )
    notifications = []
    publish = app.state.live_publisher.offer_local_controls

    def capture(snapshot) -> None:
        notifications.append(snapshot)
        publish(snapshot)

    monkeypatch.setattr(app.state.live_publisher, "offer_local_controls", capture)
    with TestClient(app) as client:
        wait_for_state(client, lambda state: state.coordinator is CoordinatorCondition.READY)
        assert client.post("/api/dev/simulation/coordinator-panel/button/tap").status_code == 200
        wait_for_state(client, lambda state: state.hotspot is HotspotLifecycle.ACTIVATING)
        client.put(
            "/api/dev/simulation/coordinator-panel/hotspot-failure",
            json={"enabled": True},
        )
        client.put(
            "/api/dev/simulation/coordinator-panel/link", json={"connected": False}
        )

        notifications.clear()
        assert client.post("/api/dev/simulation/reset").status_code == 200
        starting = app.state.local_controls_service.snapshot().state
        assert starting.coordinator is CoordinatorCondition.STARTING
        assert starting.hotspot is HotspotLifecycle.DISABLED
        assert starting.panel_link is PanelLink.CONNECTED
        assert starting.client_connected is False
        assert starting.diagnostic is None
        assert starting.desired_display is PanelDisplayState.STARTING

        wait_for_state(client, lambda state: state.coordinator is CoordinatorCondition.READY)
        displays = [snapshot.state.desired_display for snapshot in notifications]
        off = displays.index(PanelDisplayState.OFF)
        starting_index = displays.index(PanelDisplayState.STARTING, off + 1)
        displays.index(PanelDisplayState.READY, starting_index + 1)
        revisions = [snapshot.revision for snapshot in notifications]
        assert revisions == sorted(set(revisions))
        assert app.state.local_controls_service.snapshot().state.desired_display is (
            PanelDisplayState.READY
        )
        assert client.post("/api/dev/simulation/coordinator-panel/button/tap").status_code == 200
        wait_for_state(client, lambda state: state.hotspot is HotspotLifecycle.ACTIVATING)


@pytest.mark.parametrize("profile", [DeploymentProfile.BENCH, DeploymentProfile.CAR])
def test_physical_profiles_do_not_install_panel_simulation_routes(
    profile: DeploymentProfile,
) -> None:
    # Route installation depends only on the closed deployment scope, so checking
    # OpenAPI avoids opening physical SocketCAN interfaces in this contract test.
    from e87canbus.deployment import deployment_spec
    from e87canbus.runners.simulation.api import install_simulation_api
    isolated = FastAPI()
    install_simulation_api(isolated, deployment_spec(profile).simulation_api)
    paths = {getattr(route, "path", "") for route in isolated.routes}
    assert not any(path.startswith("/api/dev/simulation/coordinator-panel") for path in paths)
    assert "/api/dev/simulation/coordinator/failure" not in paths


def test_failed_controller_reset_restores_authoritative_local_condition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(
        profile=DeploymentProfile.SIMULATOR,
        profile_database_path=tmp_path / "simulator.sqlite3",
    )

    async def fail_reset(_app: FastAPI, _command: object) -> int:
        raise ApiProblem(503, "controller_runtime_error", "simulated reset failure")

    with TestClient(app) as client:
        wait_for_state(client, lambda state: state.coordinator is CoordinatorCondition.READY)
        monkeypatch.setattr(simulation_commands, "submit_runtime_work", fail_reset)

        with pytest.raises(ApiProblem):
            asyncio.run(simulation_commands.run_command(app, ResetSimulation()))

        wait_for_state(client, lambda state: state.coordinator is CoordinatorCondition.READY)
        assert app.state.local_controls_service.snapshot().state.desired_display is (
            PanelDisplayState.READY
        )


def test_ready_controller_maps_through_closed_condition_adapter(tmp_path: Path) -> None:
    app = create_app(
        profile=DeploymentProfile.SIMULATOR,
        profile_database_path=tmp_path / "simulator.sqlite3",
    )
    controller = app.state.controller_loop
    assert controller_condition(controller) is CoordinatorCondition.STARTING
    with TestClient(app):
        assert controller_condition(controller) is CoordinatorCondition.READY
    assert controller_condition(controller) is CoordinatorCondition.SHUTTING_DOWN
    assert app.state.local_controls_service.snapshot().state.desired_display is (
        PanelDisplayState.OFF
    )


def test_dead_local_service_cannot_obstruct_application_cleanup(tmp_path: Path) -> None:
    app = create_app(
        profile=DeploymentProfile.SIMULATOR,
        profile_database_path=tmp_path / "simulator.sqlite3",
    )
    controller = app.state.controller_loop
    publisher = app.state.live_publisher
    with TestClient(app) as client:
        local = app.state.local_controls_service
        wait_for_state(client, lambda state: state.coordinator is CoordinatorCondition.READY)
        local.submit(CoordinatorConditionChanged(CoordinatorCondition.FAULT)).result(
            timeout=1.0
        )
        local.stop(graceful=False)

    assert controller.lifecycle is ControllerLoopLifecycle.STOPPED
    assert publisher.running is False
    assert local.snapshot().state.desired_display is PanelDisplayState.FAULT


class FailingButtonProfiles:
    def get_selected_profile(self):
        raise OSError("profile database unavailable")


def test_persistence_startup_failure_retains_panel_fault(tmp_path: Path) -> None:
    app = create_app(
        profile=DeploymentProfile.SIMULATOR,
        profile_database_path=tmp_path / "unused.sqlite3",
        profile_repository=cast(SteeringProfileRepository, object()),
        button_profile_repository=cast(ButtonProfileRepository, FailingButtonProfiles()),
        settings_repository=cast(ApplicationSettingsRepository, object()),
    )

    with pytest.raises(OSError, match="profile database unavailable"), TestClient(app):
        pass

    local = app.state.local_controls_service
    assert local.lifecycle is LocalControlsLifecycle.STOPPED
    assert local.snapshot().state.desired_display is PanelDisplayState.FAULT
    assert app.state.simulated_local_controls.panel.effective_display is PanelDisplayState.FAULT


class FailingTimerRuntime(SimulatedControllerRuntime):
    def timer(self, now: float) -> None:
        del now
        raise OSError("unexpected owner failure")


def test_unexpected_controller_owner_failure_maps_to_fault() -> None:
    config = replace(simulator_config(), tick_interval_s=0.01)
    controller = ControllerLoop(
        FailingTimerRuntime(config=config),
        deployment=deployment_spec(DeploymentProfile.SIMULATOR),
    )
    controller.mark_persistence_available()
    controller.start()
    controller.mark_ready()
    deadline = time.monotonic() + 1.0
    while controller.lifecycle is not ControllerLoopLifecycle.STOPPED:
        assert time.monotonic() < deadline
        time.sleep(0.005)

    assert controller.fatal_exit_required is True
    assert controller.fatal is True
    assert controller_condition(controller) is CoordinatorCondition.FAULT
    with pytest.raises(ControllerLoopError, match="unexpected owner failure"):
        controller.stop()


def test_authoritative_controller_fatal_health_drives_panel_fault(tmp_path: Path) -> None:
    app = create_app(
        profile=DeploymentProfile.SIMULATOR,
        profile_database_path=tmp_path / "simulator.sqlite3",
    )
    with TestClient(app) as client:
        wait_for_state(client, lambda state: state.coordinator is CoordinatorCondition.READY)
        response = client.post("/api/dev/simulation/coordinator/failure")
        assert response.status_code == 200
        assert response.json() == {
            "accepted": True,
            "boot_id": app.state.controller_loop.boot_id,
        }
        wait_for_state(client, lambda state: state.coordinator is CoordinatorCondition.FAULT)
        assert app.state.local_controls_service.snapshot().state.desired_display is (
            PanelDisplayState.FAULT
        )
        assert app.state.controller_loop.fatal is True

        assert client.post("/api/dev/simulation/reset").status_code == 200
        wait_for_state(client, lambda state: state.coordinator is CoordinatorCondition.READY)
        assert app.state.controller_loop.fatal is False
        assert app.state.local_controls_service.snapshot().state.desired_display is (
            PanelDisplayState.READY
        )
