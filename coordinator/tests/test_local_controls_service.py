from __future__ import annotations

import threading
import time
from collections.abc import Callable

import pytest
from e87canbus.local_controls import (
    CoordinatorCondition,
    CoordinatorConditionChanged,
    CoordinatorConditionPort,
    HotspotLifecycle,
    HotspotObserved,
    HotspotPort,
    LocalControlsInboxFull,
    LocalControlsInputSink,
    LocalControlsLifecycle,
    LocalControlsService,
    LocalControlsSnapshot,
    PanelButtonPressed,
    PanelDisplayState,
    PanelLink,
    PanelLinkChanged,
    PanelPort,
)


class FakePanel(PanelPort):
    def __init__(self) -> None:
        self.submit: LocalControlsInputSink | None = None
        self.displays: list[PanelDisplayState] = []
        self.closed = False
        self.fail_display = False
        self.block_display = False
        self.display_entered = threading.Event()
        self.release_display = threading.Event()

    def start(self, submit: LocalControlsInputSink) -> None:
        self.submit = submit

    def set_display(self, display: PanelDisplayState) -> None:
        self.display_entered.set()
        if self.block_display:
            assert self.release_display.wait(timeout=2.0)
        if self.fail_display:
            raise RuntimeError("panel unavailable")
        self.displays.append(display)

    def poll(self, now: float) -> None:
        del now

    def close(self) -> None:
        self.closed = True


class FakeHotspot(HotspotPort):
    def __init__(self) -> None:
        self.submit: LocalControlsInputSink | None = None
        self.activations = 0
        self.deactivations = 0
        self.closed = False
        self.fail_activation = False
        self.fail_deactivation = False

    def start(self, submit: LocalControlsInputSink) -> None:
        self.submit = submit

    def activate(self) -> None:
        self.activations += 1
        if self.fail_activation:
            raise RuntimeError("hotspot activation failed")

    def deactivate(self) -> None:
        self.deactivations += 1
        if self.fail_deactivation:
            raise RuntimeError("hotspot deactivation failed")

    def poll(self, now: float) -> None:
        del now

    def close(self) -> None:
        self.closed = True


class FakeCondition(CoordinatorConditionPort):
    def __init__(self) -> None:
        self.submit: LocalControlsInputSink | None = None
        self.closed = False

    def start(self, submit: LocalControlsInputSink) -> None:
        self.submit = submit

    def poll(self, now: float) -> None:
        del now

    def close(self) -> None:
        self.closed = True


def _service(
    *,
    panel: FakePanel | None = None,
    hotspot: FakeHotspot | None = None,
    condition: FakeCondition | None = None,
    notification: Callable[[LocalControlsSnapshot], None] | None = None,
    inbox_capacity: int = 32,
    refresh_interval: float = 10.0,
) -> tuple[LocalControlsService, FakePanel, FakeHotspot, FakeCondition]:
    panel = panel or FakePanel()
    hotspot = hotspot or FakeHotspot()
    condition = condition or FakeCondition()
    service = LocalControlsService(
        panel=panel,
        hotspot=hotspot,
        coordinator_condition=condition,
        inbox_capacity=inbox_capacity,
        panel_refresh_interval_s=refresh_interval,
    )
    service.start(notification)
    return service, panel, hotspot, condition


def _wait_until(predicate: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 1.0
    while not predicate():
        if time.monotonic() >= deadline:
            pytest.fail("condition was not reached")
        time.sleep(0.005)


def test_service_owns_boot_revision_snapshot_and_notifications() -> None:
    notifications: list[LocalControlsSnapshot] = []
    service, panel, _, _ = _service(notification=notifications.append)
    try:
        initial = service.snapshot()
        revision = service.submit(
            CoordinatorConditionChanged(CoordinatorCondition.READY)
        ).result(timeout=1.0)

        assert initial.revision == 1
        assert initial.boot_id
        assert revision == 2
        assert service.snapshot().state.desired_display is PanelDisplayState.READY
        assert [item.revision for item in notifications] == [1, 2]
        assert panel.displays == [PanelDisplayState.STARTING, PanelDisplayState.READY]
    finally:
        service.stop()


def test_button_transition_and_adapter_observations_converge() -> None:
    service, _, hotspot, _ = _service()
    try:
        service.submit(CoordinatorConditionChanged(CoordinatorCondition.READY)).result(timeout=1.0)
        service.submit(PanelButtonPressed(sequence=1)).result(timeout=1.0)
        assert service.snapshot().state.hotspot is HotspotLifecycle.ACTIVATING
        assert hotspot.activations == 1

        assert hotspot.submit is not None
        assert hotspot.submit(HotspotObserved(HotspotLifecycle.ACTIVE))
        _wait_until(lambda: service.snapshot().state.hotspot is HotspotLifecycle.ACTIVE)
        service.submit(PanelButtonPressed(sequence=2)).result(timeout=1.0)

        assert hotspot.deactivations == 1
        assert service.snapshot().state.hotspot is HotspotLifecycle.DEACTIVATING
    finally:
        service.stop()


def test_hotspot_activation_failure_immediately_commands_fault_display() -> None:
    hotspot = FakeHotspot()
    hotspot.fail_activation = True
    service, panel, _, _ = _service(hotspot=hotspot)
    try:
        service.submit(CoordinatorConditionChanged(CoordinatorCondition.READY)).result(timeout=1.0)
        service.submit(PanelButtonPressed(sequence=1)).result(timeout=1.0)

        snapshot = service.snapshot()
        assert service.lifecycle is LocalControlsLifecycle.RUNNING
        assert snapshot.state.hotspot is HotspotLifecycle.FAULT
        assert snapshot.state.diagnostic == "hotspot activation failed"
        assert panel.displays[-1] is PanelDisplayState.FAULT

        assert hotspot.submit is not None
        assert hotspot.submit(HotspotObserved(HotspotLifecycle.DISABLED))
        _wait_until(lambda: service.snapshot().state.hotspot is HotspotLifecycle.DISABLED)
        assert service.snapshot().state.diagnostic is None
    finally:
        service.stop()


def test_hotspot_deactivation_failure_immediately_commands_fault_display() -> None:
    hotspot = FakeHotspot()
    service, panel, _, _ = _service(hotspot=hotspot)
    try:
        service.submit(CoordinatorConditionChanged(CoordinatorCondition.READY)).result(timeout=1.0)
        assert hotspot.submit is not None
        assert hotspot.submit(HotspotObserved(HotspotLifecycle.ACTIVE))
        _wait_until(lambda: service.snapshot().state.hotspot is HotspotLifecycle.ACTIVE)

        hotspot.fail_deactivation = True
        service.submit(PanelButtonPressed(sequence=1)).result(timeout=1.0)

        snapshot = service.snapshot()
        assert service.lifecycle is LocalControlsLifecycle.RUNNING
        assert snapshot.state.hotspot is HotspotLifecycle.FAULT
        assert snapshot.state.diagnostic == "hotspot deactivation failed"
        assert panel.displays[-1] is PanelDisplayState.FAULT
    finally:
        service.stop()


def test_panel_failure_changes_only_local_effective_display_and_can_recover() -> None:
    panel = FakePanel()
    service, _, _, _ = _service(panel=panel)
    try:
        panel.fail_display = True
        service.submit(CoordinatorConditionChanged(CoordinatorCondition.READY)).result(timeout=1.0)

        failed = service.snapshot()
        assert service.lifecycle is LocalControlsLifecycle.RUNNING
        assert failed.state.desired_display is PanelDisplayState.READY
        assert failed.state.effective_display is PanelDisplayState.FAULT
        assert failed.state.panel_link is PanelLink.DISCONNECTED
        assert failed.state.diagnostic == "panel unavailable"

        panel.fail_display = False
        service.submit(PanelLinkChanged(PanelLink.CONNECTED)).result(timeout=1.0)
        recovered = service.snapshot()
        assert recovered.state.effective_display is PanelDisplayState.READY
        assert recovered.state.diagnostic is None
        assert panel.displays[-1] is PanelDisplayState.READY
    finally:
        service.stop()


def test_panel_link_reconnection_sends_latest_complete_state() -> None:
    service, panel, _, _ = _service()
    try:
        service.submit(PanelLinkChanged(PanelLink.DISCONNECTED)).result(timeout=1.0)
        service.submit(CoordinatorConditionChanged(CoordinatorCondition.READY)).result(timeout=1.0)
        assert service.snapshot().state.desired_display is PanelDisplayState.READY
        assert service.snapshot().state.effective_display is PanelDisplayState.FAULT

        count_before_reconnect = len(panel.displays)
        service.submit(PanelLinkChanged(PanelLink.CONNECTED)).result(timeout=1.0)
        assert panel.displays[count_before_reconnect:] == [PanelDisplayState.READY]
        assert service.snapshot().state.effective_display is PanelDisplayState.READY
    finally:
        service.stop()


def test_complete_display_is_refreshed_on_a_service_deadline() -> None:
    service, panel, _, _ = _service(refresh_interval=0.02)
    try:
        _wait_until(lambda: len(panel.displays) >= 2)
        assert panel.displays[:2] == [PanelDisplayState.STARTING, PanelDisplayState.STARTING]
        assert service.snapshot().revision == 1
    finally:
        service.stop()


def test_bounded_inbox_reports_overload_and_owner_recovers() -> None:
    panel = FakePanel()
    service, _, _, _ = _service(panel=panel, inbox_capacity=1)
    try:
        panel.block_display = True
        panel.display_entered.clear()
        first = service.submit(CoordinatorConditionChanged(CoordinatorCondition.READY))
        assert panel.display_entered.wait(timeout=1.0)
        queued = service.submit(CoordinatorConditionChanged(CoordinatorCondition.STARTING))
        with pytest.raises(LocalControlsInboxFull):
            service.submit(CoordinatorConditionChanged(CoordinatorCondition.FAULT))

        panel.release_display.set()
        first.result(timeout=1.0)
        queued.result(timeout=1.0)
        _wait_until(lambda: service.snapshot().state.inbox_overflowed)
        assert service.lifecycle is LocalControlsLifecycle.RUNNING
        assert service.snapshot().state.diagnostic == "local-controls inbox capacity 1 exceeded"
    finally:
        panel.release_display.set()
        service.stop()


def test_shutdown_turns_panel_off_and_closes_every_port() -> None:
    service, panel, hotspot, condition = _service()

    service.stop()

    assert service.lifecycle is LocalControlsLifecycle.STOPPED
    assert service.snapshot().state.desired_display is PanelDisplayState.OFF
    assert panel.displays[-1] is PanelDisplayState.OFF
    assert panel.closed and hotspot.closed and condition.closed


def test_failure_teardown_retains_fault_while_closing_every_port() -> None:
    service, panel, hotspot, condition = _service()
    service.submit(CoordinatorConditionChanged(CoordinatorCondition.FAULT)).result(
        timeout=1.0
    )

    service.stop(graceful=False)

    assert service.lifecycle is LocalControlsLifecycle.STOPPED
    assert service.snapshot().state.desired_display is PanelDisplayState.FAULT
    assert panel.displays[-1] is PanelDisplayState.FAULT
    assert panel.closed and hotspot.closed and condition.closed
