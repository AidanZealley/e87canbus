import logging

import pytest
from e87canbus import live
from e87canbus.cli.main import main
from e87canbus.config import AppConfig


def test_live_cli_returns_failure_and_logs_missing_interface(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail_without_can(config: AppConfig) -> int:
        del config
        logging.getLogger("e87canbus.live").error(
            "failed to open SocketCAN interface can0: No such device"
        )
        return 1

    monkeypatch.setattr(live, "run_live", fail_without_can)

    with caplog.at_level(logging.ERROR):
        result = main([])

    assert result == 1
    assert "failed to open SocketCAN interface can0" in caplog.text
