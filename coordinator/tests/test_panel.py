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

    def activate(self) -> None:
        self.activations += 1
        self.observation = HotspotObservation.STARTING

    def deactivate(self) -> None:
        self.observation = HotspotObservation.STOPPING

    def observe(self) -> HotspotObservation:
        return self.observation


class RecordingOutput:
    def __init__(self) -> None:
        self.states: list[PanelDisplay] = []

    def display(self, state: PanelDisplay) -> None:
        self.states.append(state)


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


def test_button_is_ignored_until_coordinator_is_ready() -> None:
    backend = FakeBackend()
    panel = PanelService(HotspotService(backend), RecordingOutput())

    panel.button_pressed()
    panel.set_coordinator_status(CoordinatorStatus.READY)
    panel.button_pressed()

    assert backend.activations == 1
    assert panel.display is PanelDisplay.HOTSPOT_WAITING


def test_refresh_projects_backend_changes_to_the_same_output_state() -> None:
    backend = FakeBackend()
    output = RecordingOutput()
    panel = PanelService(HotspotService(backend), output)
    panel.set_coordinator_status(CoordinatorStatus.READY)

    backend.observation = HotspotObservation.CONNECTED
    panel.refresh()

    assert panel.display is PanelDisplay.HOTSPOT_CONNECTED
    assert output.states[-1] is panel.display
