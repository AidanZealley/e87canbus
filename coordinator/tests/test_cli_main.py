from __future__ import annotations

import json
import threading
import time

import pytest
from e87canbus.api import main as api_main
from e87canbus.cli import main as cli
from e87canbus.config import NetworkConfigError
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


def test_cli_reports_explicit_disabled_role_in_dry_run(
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
                "disabled",
                "--dry-run",
            )
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)

    assert output["device_adapters"] == [
        {"role": "button_pad", "source": "disabled"}
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


class TestNetworkConfigurationCli:
    def test_dry_run_reports_enabled_and_tx_networks(
        self,
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
                    "live",
                    "--enabled-networks",
                    "kcan",
                    "--tx-networks",
                    "kcan",
                    "--dry-run",
                )
            )
            == 0
        )
        output = json.loads(capsys.readouterr().out)

        assert output["enabled_networks"] == ["kcan"]
        assert output["tx_networks"] == ["kcan"]

    def test_dry_run_reports_all_three_networks(
        self,
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
                    "live",
                    "--enabled-networks",
                    "kcan,ptcan,fcan",
                    "--tx-networks",
                    "kcan",
                    "--dry-run",
                )
            )
            == 0
        )
        output = json.loads(capsys.readouterr().out)

        assert output["enabled_networks"] == ["kcan", "ptcan", "fcan"]
        assert output["tx_networks"] == ["kcan"]

    def test_environment_variable_fallback(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("E87CANBUS_ENABLED_NETWORKS", "kcan,ptcan")
        monkeypatch.setenv("E87CANBUS_TX_NETWORKS", "kcan")
        monkeypatch.setattr(
            cli.uvicorn,
            "run",
            lambda *_args, **_kwargs: pytest.fail("started"),
        )

        assert cli.main(("run", "--mode", "live", "--dry-run")) == 0
        output = json.loads(capsys.readouterr().out)

        assert output["enabled_networks"] == ["kcan", "ptcan"]
        assert output["tx_networks"] == ["kcan"]

    def test_cli_overrides_environment_variable(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("E87CANBUS_ENABLED_NETWORKS", "kcan,ptcan,fcan")
        monkeypatch.setenv("E87CANBUS_TX_NETWORKS", "kcan,ptcan")
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
                    "live",
                    "--enabled-networks",
                    "kcan",
                    "--tx-networks",
                    "kcan",
                    "--dry-run",
                )
            )
            == 0
        )
        output = json.loads(capsys.readouterr().out)

        assert output["enabled_networks"] == ["kcan"]
        assert output["tx_networks"] == ["kcan"]

    def test_tx_network_not_enabled_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            cli.uvicorn,
            "run",
            lambda *_args, **_kwargs: pytest.fail("started"),
        )

        with pytest.raises(NetworkConfigError, match="TX network not enabled"):
            cli.main(
                (
                    "run",
                    "--mode",
                    "live",
                    "--enabled-networks",
                    "kcan",
                    "--tx-networks",
                    "ptcan",
                    "--dry-run",
                )
            )

    def test_simulated_mode_ignores_network_config(
        self,
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
                    "--enabled-networks",
                    "kcan",
                    "--tx-networks",
                    "kcan",
                    "--dry-run",
                )
            )
            == 0
        )
        output = json.loads(capsys.readouterr().out)

        assert output["mode"] == "simulated"
        # In simulated mode, all networks remain enabled (simulator_config behavior)
        # The enabled_networks/tx_networks are still reported but don't change config
        assert "enabled_networks" in output

    def test_empty_tx_networks_valid(
        self,
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
                    "live",
                    "--enabled-networks",
                    "kcan",
                    "--dry-run",
                )
            )
            == 0
        )
        output = json.loads(capsys.readouterr().out)

        assert output["enabled_networks"] == ["kcan"]
        assert output["tx_networks"] == []
