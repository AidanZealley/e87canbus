from __future__ import annotations

from e87canbus.hotspot import HotspotObservation, HotspotService, HotspotStatus
from e87canbus.panel import (
    CoordinatorStatus,
    PanelDisplay,
    PanelService,
    derive_display,
)


class FakeBackend:
    def __init__(self) -> None:
        self.observation = HotspotObservation.DISABLED
        self.activations = 0
        self.observations = 0

    def activate(self) -> None:
        self.activations += 1
        self.observation = HotspotObservation.STARTING

    def deactivate(self) -> None:
        self.observation = HotspotObservation.STOPPING

    def observe(self) -> HotspotObservation:
        self.observations += 1
        return self.observation


def test_display_priority_selects_the_six_visible_states() -> None:
    examples = (
        (CoordinatorStatus.OFF, HotspotStatus.FAILED, PanelDisplay.OFF),
        (CoordinatorStatus.FAULT, HotspotStatus.CONNECTED, PanelDisplay.FAULT),
        (CoordinatorStatus.READY, HotspotStatus.FAILED, PanelDisplay.FAULT),
        (CoordinatorStatus.STARTING, HotspotStatus.CONNECTED, PanelDisplay.STARTING),
        (CoordinatorStatus.READY, HotspotStatus.CONNECTED, PanelDisplay.HOTSPOT_CONNECTED),
        (CoordinatorStatus.READY, HotspotStatus.STARTING, PanelDisplay.HOTSPOT_WAITING),
        (CoordinatorStatus.READY, HotspotStatus.WAITING, PanelDisplay.HOTSPOT_WAITING),
        (CoordinatorStatus.READY, HotspotStatus.DISABLED, PanelDisplay.READY),
    )

    for coordinator, hotspot, expected in examples:
        assert derive_display(coordinator, hotspot) is expected


def test_button_uses_event_time_status_before_observing_or_toggling_hotspot() -> None:
    backend = FakeBackend()
    panel = PanelService(HotspotService(backend))
    panel.set_coordinator_status(CoordinatorStatus.READY)
    observations_before_press = backend.observations

    panel.button_pressed(CoordinatorStatus.STARTING)

    assert backend.activations == 0
    assert backend.observations == observations_before_press

    panel.button_pressed(CoordinatorStatus.READY)

    assert backend.activations == 1
    assert panel.display is PanelDisplay.HOTSPOT_WAITING


def test_refresh_projects_backend_changes_to_the_display() -> None:
    backend = FakeBackend()
    panel = PanelService(HotspotService(backend))
    panel.set_coordinator_status(CoordinatorStatus.READY)

    backend.observation = HotspotObservation.CONNECTED
    panel.refresh()

    assert panel.display is PanelDisplay.HOTSPOT_CONNECTED
