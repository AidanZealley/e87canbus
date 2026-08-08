"""NetworkManager backend for the one provisioned coordinator hotspot."""

from __future__ import annotations

import subprocess

from e87canbus.hotspot import HotspotObservation

HOTSPOT_CONNECTION = "e87canbus-hotspot"
WIFI_INTERFACE = "wlan0"
COMMAND_TIMEOUT_S = 5.0


class NetworkManagerHotspotBackend:
    def activate(self) -> None:
        self._run("nmcli", "--wait", "0", "connection", "up", "id", HOTSPOT_CONNECTION)

    def deactivate(self) -> None:
        self._run("nmcli", "connection", "down", "id", HOTSPOT_CONNECTION)

    def observe(self) -> HotspotObservation:
        result = self._run(
            "nmcli",
            "--get-values",
            "GENERAL.STATE",
            "connection",
            "show",
            "id",
            HOTSPOT_CONNECTION,
        )
        state = result.stdout.strip().casefold()
        if state == "activating":
            return HotspotObservation.STARTING
        if state == "deactivating":
            return HotspotObservation.STOPPING
        if state != "activated":
            return HotspotObservation.DISABLED

        stations = self._run("iw", "dev", WIFI_INTERFACE, "station", "dump")
        if any(line.lstrip().startswith("Station ") for line in stations.stdout.splitlines()):
            return HotspotObservation.CONNECTED
        return HotspotObservation.WAITING

    @staticmethod
    def _run(*command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_S,
        )
