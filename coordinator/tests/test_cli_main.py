from __future__ import annotations

from typing import Any

import pytest
from e87canbus.api import main as api_main
from e87canbus.cli import main as cli
from e87canbus.composition import ControllerMode


def test_canonical_cli_selects_live_api_without_opening_adapters_before_lifespan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        cli.uvicorn,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    result = cli.main(("run", "--mode", "live"))

    assert result == 0
    assert api_main.app.state.controller_mode is ControllerMode.LIVE
    assert calls[0][0] == ("e87canbus.api.main:app",)


def test_dry_run_reports_selected_mode_without_starting_server(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli.uvicorn, "run", lambda *_args, **_kwargs: pytest.fail("started"))

    assert cli.main(("run", "--mode", "simulated", "--dry-run")) == 0
    assert '"mode": "simulated"' in capsys.readouterr().out
