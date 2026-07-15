from __future__ import annotations

import json
import threading
import time

import pytest
from e87canbus.api import main as api_main
from e87canbus.cli import main as cli
from e87canbus.service import ControllerMode


def test_canonical_cli_selects_live_api_without_opening_adapters_before_lifespan(
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

    monkeypatch.setattr(cli.uvicorn, "Server", FakeServer)

    result = cli.main(("run", "--mode", "live"))

    assert result == 0
    assert api_main.app.state.controller_mode is ControllerMode.LIVE
    assert len(calls) == 1


def test_dry_run_reports_selected_mode_without_starting_server(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_app = api_main.app
    monkeypatch.delenv(cli.PROFILE_DATABASE_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.delenv(cli.CONTROLLER_MODE_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.setattr(
        cli.uvicorn,
        "run",
        lambda *_args, **_kwargs: pytest.fail("started"),
    )

    assert cli.main(("run", "--mode", "simulated", "--dry-run")) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["mode"] == "simulated"
    assert output["device_adapters"] == [
        {"role": "button_pad", "source": "emulated"}
    ]
    assert api_main.app is original_app
    assert cli.PROFILE_DATABASE_ENVIRONMENT_VARIABLE not in cli.os.environ
    assert cli.CONTROLLER_MODE_ENVIRONMENT_VARIABLE not in cli.os.environ


def test_cli_reports_explicit_observer_role_in_dry_run(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli.uvicorn,
        "run",
        lambda *_args, **_kwargs: pytest.fail("started"),
    )

    assert (
        cli.main(
            (
                "run",
                "--mode",
                "simulated",
                "--button-pad-source",
                "observer",
                "--dry-run",
            )
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)

    assert output["device_adapters"] == [
        {"role": "button_pad", "source": "observer"}
    ]


def test_cli_rejects_physical_button_pad_in_simulation() -> None:
    with pytest.raises(
        ValueError,
        match="physical button pad requires live SocketCAN K-CAN",
    ):
        cli.main(
            (
                "run",
                "--mode",
                "simulated",
                "--button-pad-source",
                "physical",
                "--dry-run",
            )
        )


def test_live_cli_rejects_unauthenticated_non_loopback_bind() -> None:
    with pytest.raises(ValueError, match="loopback"):
        cli.main(("run", "--mode", "live", "--host", "0.0.0.0", "--dry-run"))


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

    assert cli.main(("run", "--mode", "live")) == 1


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

    assert cli.main(("run", "--mode", "live")) == 1
