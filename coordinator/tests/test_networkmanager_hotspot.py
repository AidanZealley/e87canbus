from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import Any

import pytest
from e87canbus.adapters.networkmanager_hotspot import NetworkManagerHotspotBackend
from e87canbus.hotspot import HotspotObservation


def test_backend_uses_only_fixed_connection_for_activation_and_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []

    def run(command: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(tuple(command))
        assert kwargs["check"] is True
        return subprocess.CompletedProcess(command, 0, stdout="")

    monkeypatch.setattr(subprocess, "run", run)
    backend = NetworkManagerHotspotBackend()

    backend.activate()
    backend.deactivate()

    assert commands == [
        (
            "nmcli",
            "--wait",
            "0",
            "connection",
            "up",
            "id",
            "e87canbus-hotspot",
        ),
        ("nmcli", "connection", "down", "id", "e87canbus-hotspot"),
    ]


@pytest.mark.parametrize(
    ("networkmanager_state", "stations", "expected"),
    [
        ("deactivated\n", "", HotspotObservation.DISABLED),
        ("activating\n", "", HotspotObservation.STARTING),
        ("deactivating\n", "", HotspotObservation.STOPPING),
        ("activated\n", "", HotspotObservation.WAITING),
        (
            "activated\n",
            "Station aa:bb:cc:dd:ee:ff (on wlan0)\n",
            HotspotObservation.CONNECTED,
        ),
    ],
)
def test_backend_maps_networkmanager_and_station_observations(
    monkeypatch: pytest.MonkeyPatch,
    networkmanager_state: str,
    stations: str,
    expected: HotspotObservation,
) -> None:
    def run(command: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del kwargs
        stdout = stations if command[0] == "iw" else networkmanager_state
        return subprocess.CompletedProcess(command, 0, stdout=stdout)

    monkeypatch.setattr(subprocess, "run", run)

    assert NetworkManagerHotspotBackend().observe() is expected
