"""NetworkManager backend for the one provisioned coordinator hotspot."""

from __future__ import annotations

import subprocess

from e87canbus.hotspot import HotspotObservation

SUDO = "/usr/bin/sudo"
HOTSPOT_HELPER = "/usr/local/libexec/e87canbus-hotspot"
COMMAND_TIMEOUT_S = 5.0


class NetworkManagerHotspotBackend:
    def activate(self) -> None:
        self._run("activate")

    def deactivate(self) -> None:
        self._run("deactivate")

    def observe(self) -> HotspotObservation:
        result = self._run("state")
        state = result.stdout.strip().casefold()
        if state == "activating":
            return HotspotObservation.STARTING
        if state == "deactivating":
            return HotspotObservation.STOPPING
        if state != "activated":
            return HotspotObservation.DISABLED

        stations = self._run("stations")
        if any(line.lstrip().startswith("Station ") for line in stations.stdout.splitlines()):
            return HotspotObservation.CONNECTED
        return HotspotObservation.WAITING

    @staticmethod
    def _run(action: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (SUDO, "-n", HOTSPOT_HELPER, action),
            check=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_S,
        )
