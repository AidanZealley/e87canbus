from __future__ import annotations

import json
import threading
import time

import pytest
from e87canbus.api import main as api_main
from e87canbus.cli import main as cli
from e87canbus.deployment import DeploymentProfile


def test_canonical_cli_selects_car_profile_without_opening_adapters_before_lifespan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    class FakeServer:
        should_exit = False
        started = True

        def __init__(self, config: object) -> None:
            calls.append(config)

        def run(self) -> None:
            return

    monkeypatch.delenv(cli.DEPLOYMENT_PROFILE_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.setattr(cli.uvicorn, "Server", FakeServer)

    assert cli.main(("run", "--profile", "car")) == 0
    assert api_main.app.state.deployment_profile is DeploymentProfile.CAR
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("profile", "transport", "simulation_api"),
    [
        ("car", "socketcan", "none"),
        ("bench", "socketcan", "vehicle"),
        ("simulator", "in_memory", "full"),
    ],
)
def test_dry_run_reports_closed_profile(
    profile: str,
    transport: str,
    simulation_api: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(cli.DEPLOYMENT_PROFILE_ENVIRONMENT_VARIABLE, raising=False)

    assert cli.main(("run", "--profile", profile, "--dry-run")) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["profile"] == profile
    assert output["transport"] == transport
    assert output["simulation_api"] == simulation_api
    assert output["device_adapters"]


def test_profile_environment_variable_is_used_for_dry_run(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(cli.DEPLOYMENT_PROFILE_ENVIRONMENT_VARIABLE, "bench")

    assert cli.main(("run", "--dry-run")) == 0
    assert json.loads(capsys.readouterr().out)["profile"] == "bench"


def test_live_profile_rejects_unauthenticated_non_loopback_bind() -> None:
    with pytest.raises(ValueError, match="loopback"):
        cli.main(
            (
                "run",
                "--profile",
                "car",
                "--host",
                "0.0.0.0",
                "--dry-run",
            )
        )


def test_fatal_controller_stop_makes_canonical_cli_return_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FatalService:
        stopped_event = threading.Event()
        fatal_exit_required = False

    class FatalServer:
        should_exit = False
        started = True

        def __init__(self, _config: object) -> None:
            pass

        def run(self) -> None:
            service = api_main.app.state.controller_service
            assert service is fatal_service
            service.fatal_exit_required = True
            service.stopped_event.set()
            deadline = time.monotonic() + 1.0
            while not self.should_exit and time.monotonic() < deadline:
                time.sleep(0.005)

    fatal_service = FatalService()
    original_create_app = cli.create_app

    def create_app_with_fatal_service(**kwargs):
        app = original_create_app(**kwargs)
        app.state.controller_service = fatal_service
        return app

    monkeypatch.setattr(cli, "create_app", create_app_with_fatal_service)
    monkeypatch.setattr(cli.uvicorn, "Server", FatalServer)

    assert cli.main(("run", "--profile", "car")) == 1


def test_canonical_cli_returns_nonzero_when_uvicorn_never_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StartupFailedServer:
        should_exit = False
        started = False

        def __init__(self, _config: object) -> None:
            pass

        def run(self) -> None:
            return

    monkeypatch.setattr(cli.uvicorn, "Server", StartupFailedServer)

    assert cli.main(("run", "--profile", "car")) == 1


def test_profile_names_are_stable() -> None:
    assert tuple(DeploymentProfile) == (
        DeploymentProfile.CAR,
        DeploymentProfile.BENCH,
        DeploymentProfile.SIMULATOR,
    )
