"""Pure state and transitions for the coordinator's local controls."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

MAX_DIAGNOSTIC_LENGTH = 160


class CoordinatorCondition(StrEnum):
    STARTING = "starting"
    READY = "ready"
    FAULT = "fault"
    SHUTTING_DOWN = "shutting_down"


class HotspotLifecycle(StrEnum):
    DISABLED = "disabled"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    FAULT = "fault"


class PanelDisplayState(StrEnum):
    STARTING = "starting"
    READY = "ready"
    HOTSPOT_WAITING = "hotspot_waiting"
    HOTSPOT_CONNECTED = "hotspot_connected"
    FAULT = "fault"
    OFF = "off"


class PanelLink(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True)
class PanelInputs:
    coordinator: CoordinatorCondition
    hotspot: HotspotLifecycle
    client_connected: bool


def derive_panel_state(inputs: PanelInputs) -> PanelDisplayState:
    """Choose one semantic display using the product's fixed priority order."""

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


@dataclass(frozen=True)
class LocalControlsState:
    coordinator: CoordinatorCondition = CoordinatorCondition.STARTING
    hotspot: HotspotLifecycle = HotspotLifecycle.DISABLED
    client_connected: bool = False
    panel_link: PanelLink = PanelLink.CONNECTED
    desired_display: PanelDisplayState = PanelDisplayState.STARTING
    effective_display: PanelDisplayState = PanelDisplayState.STARTING
    last_button_sequence: int | None = None
    panel_diagnostic: str | None = None
    hotspot_diagnostic: str | None = None
    service_diagnostic: str | None = None
    inbox_overflowed: bool = False

    @property
    def diagnostic(self) -> str | None:
        return self.service_diagnostic or self.hotspot_diagnostic or self.panel_diagnostic


@dataclass(frozen=True)
class CoordinatorConditionChanged:
    condition: CoordinatorCondition


@dataclass(frozen=True)
class PanelButtonPressed:
    sequence: int


@dataclass(frozen=True)
class PanelLinkChanged:
    link: PanelLink


@dataclass(frozen=True)
class HotspotObserved:
    lifecycle: HotspotLifecycle
    client_connected: bool = False


@dataclass(frozen=True)
class PanelAdapterFailed:
    message: str


@dataclass(frozen=True)
class HotspotAdapterFailed:
    message: str


@dataclass(frozen=True)
class InboxOverloaded:
    capacity: int


@dataclass(frozen=True)
class PanelRefreshDue:
    pass


@dataclass(frozen=True)
class ShutdownRequested:
    pass


LocalControlsEvent = (
    CoordinatorConditionChanged
    | PanelButtonPressed
    | PanelLinkChanged
    | HotspotObserved
    | PanelAdapterFailed
    | HotspotAdapterFailed
    | InboxOverloaded
    | PanelRefreshDue
    | ShutdownRequested
)


@dataclass(frozen=True)
class SetPanelDisplay:
    display: PanelDisplayState


@dataclass(frozen=True)
class ActivateHotspot:
    pass


@dataclass(frozen=True)
class DeactivateHotspot:
    pass


LocalControlsEffect = SetPanelDisplay | ActivateHotspot | DeactivateHotspot


@dataclass(frozen=True)
class LocalControlsTransition:
    state: LocalControlsState
    effects: tuple[LocalControlsEffect, ...] = ()


def reduce_local_controls(
    state: LocalControlsState,
    event: LocalControlsEvent,
) -> LocalControlsTransition:
    """Apply one observation while keeping all product decisions in this pure function."""

    effects: list[LocalControlsEffect] = []
    next_state = state
    force_panel_refresh = isinstance(event, PanelRefreshDue)

    if isinstance(event, CoordinatorConditionChanged):
        next_state = replace(state, coordinator=event.condition)
    elif isinstance(event, PanelButtonPressed):
        if event.sequence == state.last_button_sequence:
            return LocalControlsTransition(state)
        next_state = replace(state, last_button_sequence=event.sequence)
        if state.coordinator is CoordinatorCondition.READY:
            if state.hotspot is HotspotLifecycle.DISABLED:
                next_state = replace(next_state, hotspot=HotspotLifecycle.ACTIVATING)
                effects.append(ActivateHotspot())
            elif state.hotspot is HotspotLifecycle.ACTIVE:
                next_state = replace(
                    next_state,
                    hotspot=HotspotLifecycle.DEACTIVATING,
                    client_connected=False,
                )
                effects.append(DeactivateHotspot())
    elif isinstance(event, PanelLinkChanged):
        next_state = replace(
            state,
            panel_link=event.link,
            panel_diagnostic=None if event.link is PanelLink.CONNECTED else state.panel_diagnostic,
        )
        force_panel_refresh = event.link is PanelLink.CONNECTED
    elif isinstance(event, HotspotObserved):
        next_state = replace(
            state,
            hotspot=event.lifecycle,
            client_connected=(
                event.client_connected if event.lifecycle is HotspotLifecycle.ACTIVE else False
            ),
            hotspot_diagnostic=None,
        )
    elif isinstance(event, PanelAdapterFailed):
        next_state = replace(
            state,
            panel_link=PanelLink.DISCONNECTED,
            panel_diagnostic=_bounded(event.message),
        )
    elif isinstance(event, HotspotAdapterFailed):
        next_state = replace(
            state,
            hotspot=HotspotLifecycle.FAULT,
            client_connected=False,
            hotspot_diagnostic=_bounded(event.message),
        )
    elif isinstance(event, InboxOverloaded):
        next_state = replace(
            state,
            inbox_overflowed=True,
            service_diagnostic=f"local-controls inbox capacity {event.capacity} exceeded",
        )
    elif isinstance(event, ShutdownRequested):
        next_state = replace(state, coordinator=CoordinatorCondition.SHUTTING_DOWN)

    desired = derive_panel_state(
        PanelInputs(
            coordinator=next_state.coordinator,
            hotspot=next_state.hotspot,
            client_connected=next_state.client_connected,
        )
    )
    effective = desired if next_state.panel_link is PanelLink.CONNECTED else PanelDisplayState.FAULT
    display_changed = desired is not state.desired_display
    next_state = replace(
        next_state,
        desired_display=desired,
        effective_display=effective,
    )
    if display_changed or force_panel_refresh:
        effects.append(SetPanelDisplay(desired))
    return LocalControlsTransition(next_state, tuple(effects))


def _bounded(message: str) -> str:
    return message.strip()[:MAX_DIAGNOSTIC_LENGTH]
