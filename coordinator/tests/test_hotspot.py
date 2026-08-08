from __future__ import annotations

from e87canbus.hotspot import HotspotObservation, HotspotService, HotspotStatus


class FakeBackend:
    def __init__(self, observation: HotspotObservation = HotspotObservation.DISABLED) -> None:
        self.observation = observation
        self.actions: list[str] = []
        self.failure: Exception | None = None

    def activate(self) -> None:
        self.actions.append("activate")
        if self.failure is not None:
            raise self.failure
        self.observation = HotspotObservation.STARTING

    def deactivate(self) -> None:
        self.actions.append("deactivate")
        if self.failure is not None:
            raise self.failure
        self.observation = HotspotObservation.STOPPING

    def observe(self) -> HotspotObservation:
        return self.observation


def test_toggle_activates_disabled_hotspot_and_cancels_starting_hotspot() -> None:
    backend = FakeBackend()
    hotspot = HotspotService(backend)

    hotspot.toggle()
    hotspot.toggle()

    assert backend.actions == ["activate", "deactivate"]
    assert hotspot.status() is HotspotStatus.STOPPING


def test_toggle_disables_waiting_or_connected_hotspot() -> None:
    for observation in (HotspotObservation.WAITING, HotspotObservation.CONNECTED):
        backend = FakeBackend(observation)

        HotspotService(backend).toggle()

        assert backend.actions == ["deactivate"]


def test_toggle_ignores_hotspot_while_it_is_stopping() -> None:
    backend = FakeBackend(HotspotObservation.STOPPING)

    HotspotService(backend).toggle()

    assert backend.actions == []


def test_command_failure_is_visible_and_a_press_retries_activation() -> None:
    backend = FakeBackend()
    backend.failure = OSError("activation failed")
    hotspot = HotspotService(backend)

    hotspot.toggle()

    assert hotspot.status() is HotspotStatus.FAILED

    backend.failure = None
    hotspot.toggle()

    assert backend.actions == ["activate", "activate"]
    assert hotspot.status() is HotspotStatus.STARTING


def test_toggle_uses_observed_progress_after_a_command_failure() -> None:
    backend = FakeBackend()
    backend.failure = OSError("activation failed")
    hotspot = HotspotService(backend)
    hotspot.toggle()

    backend.observation = HotspotObservation.CONNECTED
    backend.failure = None
    hotspot.toggle()

    assert backend.actions == ["activate", "deactivate"]
    assert hotspot.status() is HotspotStatus.STOPPING
