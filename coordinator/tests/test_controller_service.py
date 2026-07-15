from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path

import pytest
from e87canbus.api.main import create_app
from e87canbus.application.controller import ApplicationSnapshot
from e87canbus.composition import (
    build_live_controller_service,
    build_simulated_controller_service,
)
from e87canbus.config import CanNetwork, default_config, simulator_config
from e87canbus.device import DeviceSource
from e87canbus.runtime import (
    CoordinatorKernel,
    DiagnosticSnapshot,
    KernelStarted,
    ShutdownRequested,
)
from e87canbus.service import (
    ControllerAdapterSnapshot,
    ControllerMode,
    ControllerService,
    ControllerServiceError,
    ControllerServiceLifecycle,
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

    def start(self, submit_input: RuntimeInputSink) -> RuntimeExecution:
        del submit_input
        self.starts += 1
        self.lifecycle_events.append("start")
        commit = self.kernel.dispatch(KernelStarted(1.0))
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

    def shutdown(self, now: float) -> RuntimeExecution | None:
        self.stops += 1
        self.lifecycle_events.append("shutdown")
        commit = self.kernel.dispatch(ShutdownRequested(now))
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
    ) -> tuple[ApplicationSnapshot, DiagnosticSnapshot, ControllerAdapterSnapshot]:
        diagnostics = self.kernel.diagnostics()
        return (
            self.kernel.snapshot(),
            diagnostics,
            ControllerAdapterSnapshot(None, (3,) + (0,) * 15, (), (), None),
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
    service = ControllerService(runtime, mode=ControllerMode.LIVE)
    app = create_app(
        controller_service=service,
        mode=ControllerMode.LIVE,
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
        assert service.lifecycle is ControllerServiceLifecycle.RUNNING
        assert app.state.live_publisher.running is True

    assert (runtime.starts, runtime.stops, runtime.closes) == (1, 1, 1)
    assert runtime.lifecycle_events == ["start", "shutdown", "publisher", "close"]
    assert service.lifecycle is ControllerServiceLifecycle.STOPPED
    assert app.state.live_publisher.running is False


def test_each_controller_service_lifecycle_has_a_fresh_opaque_boot_id() -> None:
    first = ControllerService(RecordingRuntime(), mode=ControllerMode.LIVE)
    second = ControllerService(RecordingRuntime(), mode=ControllerMode.LIVE)

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
    service = ControllerService(runtime, mode=ControllerMode.LIVE)

    service.start()

    assert service.stopped_event.wait(timeout=1.0)
    assert service.fatal_exit_required is True
    assert service.ready is False
    with pytest.raises(ControllerServiceError, match="timer failed"):
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
        mode=ControllerMode.LIVE,
        config=config,
        profile_database_path=tmp_path / "app.sqlite3",
    )

    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 200
        assert client.get("/api/snapshot").status_code == 404
        assert (
            client.post(
                "/api/dev/simulation/devices/button-pad/buttons/0/tap"
            ).status_code
            == 404
        )
        assert app.state.controller_service.snapshot().diagnostics.health.fatal is False


def test_simulation_reset_changes_session_without_changing_service_boot(
    tmp_path: Path,
) -> None:
    app = create_app(profile_database_path=tmp_path / "app.sqlite3")

    with TestClient(app) as client:
        boot_id = app.state.controller_service.boot_id
        before = app.state.controller_service.snapshot()
        reset = client.post("/api/dev/simulation/reset").json()

        assert before.adapter.simulation_session_id == 1
        assert reset == {"accepted": True, "boot_id": boot_id}
        assert app.state.controller_service.snapshot().adapter.simulation_session_id == 2
        assert app.state.controller_service.boot_id == boot_id


def test_fastapi_rejects_an_injected_service_for_a_different_mode() -> None:
    service = ControllerService(RecordingRuntime(), mode=ControllerMode.LIVE)

    with pytest.raises(ValueError, match="does not match API mode"):
        create_app(
            controller_service=service,
            mode=ControllerMode.SIMULATED,
        )

    assert service.lifecycle is ControllerServiceLifecycle.CREATED


def test_live_transmitter_requires_separate_explicit_network_grant() -> None:
    with pytest.raises(ValueError, match="explicit network grant"):
        build_live_controller_service(config=simulator_config())


def test_explicit_constructors_reject_invalid_device_authority_and_output() -> None:
    with pytest.raises(ValueError, match="emulated ingress authority"):
        build_live_controller_service(button_pad_source=DeviceSource.EMULATED)

    config = simulator_config()
    config = replace(
        config,
        can_networks=tuple(
            replace(item, tx_enabled=False)
            if item.network is CanNetwork.KCAN
            else item
            for item in config.can_networks
        ),
    )
    with pytest.raises(ValueError, match="authorized simulated K-CAN output"):
        build_simulated_controller_service(config=config)


def test_repeated_app_construction_does_not_leak_controller_owner_threads(
    tmp_path: Path,
) -> None:
    baseline = {
        thread.ident for thread in threading.enumerate() if thread.name == "controller-owner"
    }

    for index in range(3):
        runtime = RecordingRuntime()
        app = create_app(
            controller_service=ControllerService(runtime, mode=ControllerMode.LIVE),
            mode=ControllerMode.LIVE,
            profile_database_path=tmp_path / f"app-{index}.sqlite3",
        )
        with TestClient(app) as client:
            assert client.get("/health/ready").status_code == 200

    remaining = {
        thread.ident for thread in threading.enumerate() if thread.name == "controller-owner"
    }
    assert remaining == baseline
