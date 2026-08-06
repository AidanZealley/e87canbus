from __future__ import annotations

import itertools

from e87canbus.local_controls import (
    ActivateHotspot,
    CoordinatorCondition,
    CoordinatorConditionChanged,
    DeactivateHotspot,
    HotspotAdapterFailed,
    HotspotLifecycle,
    HotspotObserved,
    LocalControlsState,
    PanelButtonPressed,
    PanelDisplayState,
    PanelInputs,
    PanelLink,
    PanelLinkChanged,
    SetPanelDisplay,
    ShutdownRequested,
    derive_panel_state,
    reduce_local_controls,
)


def _expected_display(inputs: PanelInputs) -> PanelDisplayState:
    if inputs.coordinator is CoordinatorCondition.SHUTTING_DOWN:
        return PanelDisplayState.OFF
    if (
        inputs.coordinator is CoordinatorCondition.FAULT
        or inputs.hotspot is HotspotLifecycle.FAULT
    ):
        return PanelDisplayState.FAULT
    if inputs.hotspot is HotspotLifecycle.ACTIVE and inputs.client_connected:
        return PanelDisplayState.HOTSPOT_CONNECTED
    if inputs.hotspot in {HotspotLifecycle.ACTIVATING, HotspotLifecycle.ACTIVE}:
        return PanelDisplayState.HOTSPOT_WAITING
    if inputs.coordinator is CoordinatorCondition.READY:
        return PanelDisplayState.READY
    return PanelDisplayState.STARTING


def test_panel_priority_is_defined_for_every_closed_input_combination() -> None:
    combinations = itertools.product(CoordinatorCondition, HotspotLifecycle, (False, True))

    for coordinator, hotspot, client_connected in combinations:
        inputs = PanelInputs(coordinator, hotspot, client_connected)
        assert derive_panel_state(inputs) is _expected_display(inputs)


def test_press_is_ignored_and_not_replayed_when_coordinator_is_not_ready() -> None:
    ignored = reduce_local_controls(LocalControlsState(), PanelButtonPressed(sequence=4))

    assert ignored.effects == ()
    assert ignored.state.hotspot is HotspotLifecycle.DISABLED
    assert ignored.state.last_button_sequence == 4

    ready = reduce_local_controls(
        ignored.state,
        CoordinatorConditionChanged(CoordinatorCondition.READY),
    )
    duplicate = reduce_local_controls(ready.state, PanelButtonPressed(sequence=4))
    accepted = reduce_local_controls(ready.state, PanelButtonPressed(sequence=5))

    assert duplicate.effects == ()
    assert accepted.state.hotspot is HotspotLifecycle.ACTIVATING
    assert accepted.effects == (
        ActivateHotspot(),
        SetPanelDisplay(PanelDisplayState.HOTSPOT_WAITING),
    )


def test_press_toggles_only_stable_hotspot_states() -> None:
    ready = LocalControlsState(
        coordinator=CoordinatorCondition.READY,
        hotspot=HotspotLifecycle.ACTIVE,
        client_connected=True,
        desired_display=PanelDisplayState.HOTSPOT_CONNECTED,
        effective_display=PanelDisplayState.HOTSPOT_CONNECTED,
    )

    deactivating = reduce_local_controls(ready, PanelButtonPressed(sequence=1))

    assert deactivating.state.hotspot is HotspotLifecycle.DEACTIVATING
    assert deactivating.state.client_connected is False
    assert deactivating.effects == (
        DeactivateHotspot(),
        SetPanelDisplay(PanelDisplayState.READY),
    )
    ignored = reduce_local_controls(deactivating.state, PanelButtonPressed(sequence=2))
    assert ignored.state.hotspot is HotspotLifecycle.DEACTIVATING
    assert ignored.effects == ()


def test_client_observation_changes_display_without_changing_hotspot_lifecycle() -> None:
    state = LocalControlsState(coordinator=CoordinatorCondition.READY)
    active = reduce_local_controls(state, HotspotObserved(HotspotLifecycle.ACTIVE))
    connected = reduce_local_controls(
        active.state,
        HotspotObserved(HotspotLifecycle.ACTIVE, client_connected=True),
    )

    assert connected.state.hotspot is HotspotLifecycle.ACTIVE
    assert connected.state.desired_display is PanelDisplayState.HOTSPOT_CONNECTED
    assert connected.effects == (SetPanelDisplay(PanelDisplayState.HOTSPOT_CONNECTED),)


def test_link_loss_changes_only_effective_display_and_reconnect_resynchronizes() -> None:
    ready = reduce_local_controls(
        LocalControlsState(),
        CoordinatorConditionChanged(CoordinatorCondition.READY),
    ).state

    disconnected = reduce_local_controls(ready, PanelLinkChanged(PanelLink.DISCONNECTED))

    assert disconnected.state.desired_display is PanelDisplayState.READY
    assert disconnected.state.effective_display is PanelDisplayState.FAULT
    assert disconnected.effects == ()

    reconnected = reduce_local_controls(
        disconnected.state,
        PanelLinkChanged(PanelLink.CONNECTED),
    )
    assert reconnected.state.effective_display is PanelDisplayState.READY
    assert reconnected.effects == (SetPanelDisplay(PanelDisplayState.READY),)


def test_hotspot_failure_is_bounded_and_a_complete_observation_recovers() -> None:
    failure = reduce_local_controls(
        LocalControlsState(coordinator=CoordinatorCondition.READY),
        HotspotAdapterFailed(" x " * 200),
    )

    assert failure.state.hotspot is HotspotLifecycle.FAULT
    assert failure.state.desired_display is PanelDisplayState.FAULT
    assert failure.state.diagnostic is not None
    assert len(failure.state.diagnostic) == 160

    recovered = reduce_local_controls(
        failure.state,
        HotspotObserved(HotspotLifecycle.DISABLED),
    )
    assert recovered.state.hotspot is HotspotLifecycle.DISABLED
    assert recovered.state.diagnostic is None
    assert recovered.state.desired_display is PanelDisplayState.READY


def test_shutdown_has_priority_over_faults_and_hotspot_state() -> None:
    faulted = LocalControlsState(
        coordinator=CoordinatorCondition.FAULT,
        hotspot=HotspotLifecycle.FAULT,
        hotspot_diagnostic="failed",
        desired_display=PanelDisplayState.FAULT,
        effective_display=PanelDisplayState.FAULT,
    )

    shutdown = reduce_local_controls(faulted, ShutdownRequested())

    assert shutdown.state.coordinator is CoordinatorCondition.SHUTTING_DOWN
    assert shutdown.state.desired_display is PanelDisplayState.OFF
    assert shutdown.effects == (SetPanelDisplay(PanelDisplayState.OFF),)
