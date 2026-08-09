"""Platform-independent coordinator panel behaviour."""

from __future__ import annotations

from enum import StrEnum

from e87canbus.hotspot import HotspotService, HotspotStatus


class CoordinatorStatus(StrEnum):
    STARTING = "starting"
    READY = "ready"
    FAULT = "fault"
    OFF = "off"


class PanelDisplay(StrEnum):
    STARTING = "starting"
    READY = "ready"
    HOTSPOT_WAITING = "hotspot_waiting"
    HOTSPOT_CONNECTED = "hotspot_connected"
    FAULT = "fault"
    OFF = "off"


def derive_display(
    coordinator_status: CoordinatorStatus,
    hotspot_status: HotspotStatus,
) -> PanelDisplay:
    """Select the one visible state using the product priority order."""
    if coordinator_status is CoordinatorStatus.OFF:
        return PanelDisplay.OFF
    if coordinator_status is CoordinatorStatus.FAULT or hotspot_status is HotspotStatus.FAILED:
        return PanelDisplay.FAULT
    if coordinator_status is CoordinatorStatus.STARTING:
        return PanelDisplay.STARTING
    if hotspot_status is HotspotStatus.CONNECTED:
        return PanelDisplay.HOTSPOT_CONNECTED
    if hotspot_status in {HotspotStatus.STARTING, HotspotStatus.WAITING}:
        return PanelDisplay.HOTSPOT_WAITING
    return PanelDisplay.READY


class PanelService:
    """Project coordinator and hotspot state to the panel's semantic display.

    Both callers poll `display` on their own schedule, so refreshing never pushes.
    """

    def __init__(self, hotspot: HotspotService) -> None:
        self._hotspot = hotspot
        self._coordinator_status = CoordinatorStatus.STARTING
        self._display = PanelDisplay.STARTING

    @property
    def display(self) -> PanelDisplay:
        return self._display

    def set_coordinator_status(self, status: CoordinatorStatus) -> None:
        self._coordinator_status = status
        self.refresh()

    def refresh(self) -> None:
        """Re-derive the display. This observes the hotspot, which can be slow."""
        self._display = derive_display(self._coordinator_status, self._hotspot.status())

    def button_pressed(self, coordinator_status: CoordinatorStatus) -> None:
        """Handle a press captured while the coordinator was in `coordinator_status`.

        A press that arrives before the coordinator is ready is ignored, not retained.
        """
        if coordinator_status is not CoordinatorStatus.READY:
            return
        self._hotspot.toggle()
        self.refresh()
