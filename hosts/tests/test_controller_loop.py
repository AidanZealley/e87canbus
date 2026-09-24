from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path

import pytest
from e87canbus.adapters.sqlite_profiles import BUILT_IN_PROFILE_ID
from e87canbus.api.main import create_app
from e87canbus.config import default_config
from e87canbus.deployment import DeploymentProfile, deployment_spec
from e87canbus.domain.controller import ApplicationSnapshot
from e87canbus.domain.steering.curves import ActiveSteeringCurve
from e87canbus.kernel import (
    CoordinatorKernel,
    DiagnosticSnapshot,
    KernelStarted,
    ShutdownRequested,
)
from e87canbus.runners.composition import (
    build_live_controller_loop,
    build_simulated_controller_loop,
)
from e87canbus.service import (
    ControllerLoop,
    ControllerLoopError,
    ControllerLoopLifecycle,
    RuntimeExecution,
    RuntimeInputSink,
)
from fastapi.testclient import TestClient


class RecordingRuntime:
    def __init__(self) -> None:
        self.config = replace(
            default_config(),
            can_networks=tuple(
                replace(item, enabled=False) for item in default_config().can_networks
            ),
            tick_interval_s=60.0,
        )
        self.kernel = CoordinatorKernel()
        self.starts = 0
        self.stops = 0
        self.closes = 0
        self.lifecycle_events: list[str] = []

    def configure_initial_steering_curve(self, curve: ActiveSteeringCurve) -> None:
        self.lifecycle_events.append("configure-curve")
        self.kernel.configure_initial_steering_curve(curve)

    def start(self, submit_input: RuntimeInputSink) -> RuntimeExecution:
        del submit_input
        self.starts += 1
        self.lifecycle_events.append("start")
        commit = self.kernel.dispatch(KernelStarted())
        assert commit is not None
        return RuntimeExecution(
            changed_topics=commit.changed_topics,
            commit_count=1,
        )

    def execute(self, work: object) -> RuntimeExecution:
        raise TypeError(f"unsupported test work: {work!r}")

    def timer(self, now: float) -> RuntimeExecution | None:
        del now
        return None

    def shutdown(self) -> RuntimeExecution | None:
        self.stops += 1
        self.lifecycle_events.append("shutdown")
        commit = self.kernel.dispatch(ShutdownRequested())
        if commit is None:
            return None
        return RuntimeExecution(
            changed_topics=commit.changed_topics,
            commit_count=1,
        )

    def close(self) -> None:
        self.closes += 1
        self.lifecycle_events.append("close")

    def projection(
        self,
    ) -> tuple[ApplicationSnapshot, DiagnosticSnapshot, int | None]:
        diagnostics = self.kernel.diagnostics()
        return (
            self.kernel.snapshot(),
            diagnostics,
            None,
        )

    @property
    def terminal(self) -> bool:
        return False


class FailingTimerRuntime(RecordingRuntime):
    def __init__(self) -> None:
        super().__init__()
        self.config = replace(self.config, tick_interval_s=0.01)

    def timer(self, now: float) -> RuntimeExecution | None:
        del now
        raise RuntimeError("timer failed")


def test_fastapi_lifespan_starts_and_stops_exactly_one_controller_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = RecordingRuntime()
    service = ControllerLoop(runtime, deployment=deployment_spec(DeploymentProfile.CAR))
    app = create_app(
        controller_loop=service,
        profile_database_path=tmp_path / "app.sqlite3",
    )
    publisher = app.state.live_publisher
    original_publisher_stop = publisher.stop

    async def record_publisher_stop() -> None:
        runtime.lifecycle_events.append("publisher")
        await original_publisher_stop()

    monkeypatch.setattr(publisher, "stop", record_publisher_stop)

    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "live"}
        assert client.get("/health/ready").json()["status"] == "ready"
        assert service.lifecycle is ControllerLoopLifecycle.RUNNING
        assert app.state.live_publisher.running is True

    assert (runtime.starts, runtime.stops, runtime.closes) == (1, 1, 1)
    assert runtime.lifecycle_events == ["start", "shutdown", "publisher", "close"]
    assert service.lifecycle is ControllerLoopLifecycle.STOPPED
    assert app.state.live_publisher.running is False


def test_each_controller_service_lifecycle_has_a_fresh_opaque_boot_id() -> None:
    first = ControllerLoop(RecordingRuntime(), deployment=deployment_spec(DeploymentProfile.CAR))
    second = ControllerLoop(RecordingRuntime(), deployment=deployment_spec(DeploymentProfile.CAR))

    first.start()
    second.start()
    try:
        assert first.boot_id
        assert second.boot_id
        assert first.boot_id != second.boot_id
        assert first.snapshot().revision == 1
    finally:
        first.stop()
        second.stop()


def test_unexpected_post_start_owner_failure_requires_fatal_process_exit() -> None:
    runtime = FailingTimerRuntime()
    service = ControllerLoop(runtime, deployment=deployment_spec(DeploymentProfile.CAR))

    service.start()

    assert service.stopped_event.wait(timeout=1.0)
    assert service.fatal_exit_required is True
    assert service.ready is False
    with pytest.raises(ControllerLoopError, match="timer failed"):
        service.stop()
    assert runtime.closes == 1


def test_live_api_can_start_with_all_can_adapters_disabled_and_has_no_dev_routes(
    tmp_path: Path,
) -> None:
    config = replace(
        default_config(),
        can_networks=tuple(replace(item, enabled=False) for item in default_config().can_networks),
    )
    app = create_app(
        controller_loop=build_live_controller_loop(config=config),
        profile_database_path=tmp_path / "app.sqlite3",
    )

    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 200
        assert client.get("/api/snapshot").status_code == 404
        assert (
            client.post("/api/dev/simulation/devices/button-pad/buttons/0/tap").status_code == 404
        )
        assert app.state.controller_loop.snapshot().diagnostics.health.fatal is False


def test_app_construction_does_not_open_or_create_the_database(tmp_path: Path) -> None:
    database = tmp_path / "missing-parent" / "application.sqlite3"

    create_app(profile=DeploymentProfile.CAR, profile_database_path=database)

    assert not database.exists()


def test_lifespan_loads_persisted_curve_before_live_controller_start(tmp_path: Path) -> None:
    database = tmp_path / "application.sqlite3"
    config = replace(
        default_config(),
        can_networks=tuple(replace(item, enabled=False) for item in default_config().can_networks),
    )
    app = create_app(
        controller_loop=build_live_controller_loop(
            config=config,
            profile_database_path=database,
        ),
        profile_database_path=database,
    )

    assert not database.exists()
    with TestClient(app):
        active = app.state.controller_loop.snapshot().application.active_steering_curve

    assert database.exists()
    assert active.saved_profile_id == BUILT_IN_PROFILE_ID


def test_simulation_reset_changes_session_without_changing_service_boot(
    tmp_path: Path,
) -> None:
    app = create_app(profile_database_path=tmp_path / "app.sqlite3")

    with TestClient(app) as client:
        boot_id = app.state.controller_loop.boot_id
        before = app.state.controller_loop.snapshot()
        reset = client.post("/api/dev/simulation/reset").json()

        assert before.simulation_session_id == 1
        assert reset == {"accepted": True, "boot_id": boot_id}
        assert app.state.controller_loop.snapshot().simulation_session_id == 2
        assert app.state.controller_loop.boot_id == boot_id


def test_fastapi_rejects_profile_configuration_with_an_injected_service() -> None:
    service = ControllerLoop(RecordingRuntime(), deployment=deployment_spec(DeploymentProfile.CAR))

    with pytest.raises(ValueError, match="inject either controller_loop"):
        create_app(
            controller_loop=service,
            profile=DeploymentProfile.SIMULATOR,
        )

    assert service.lifecycle is ControllerLoopLifecycle.CREATED


def test_simulated_constructor_keeps_vehicle_only() -> None:
    service = build_simulated_controller_loop()
    assert service.lifecycle is ControllerLoopLifecycle.CREATED


def test_repeated_app_construction_does_not_leak_controller_owner_threads(
    tmp_path: Path,
) -> None:
    baseline = {
        thread.ident for thread in threading.enumerate() if thread.name == "controller-owner"
    }

    for index in range(3):
        runtime = RecordingRuntime()
        app = create_app(
            controller_loop=ControllerLoop(
                runtime,
                deployment=deployment_spec(DeploymentProfile.CAR),
            ),
            profile_database_path=tmp_path / f"app-{index}.sqlite3",
        )
        with TestClient(app) as client:
            assert client.get("/health/ready").status_code == 200

    remaining = {
        thread.ident for thread in threading.enumerate() if thread.name == "controller-owner"
    }
    assert remaining == baseline
