"""In-memory coordinator panel and hotspot adapters for simulator mode."""

from __future__ import annotations

import threading
from collections.abc import Callable

from e87canbus.local_controls.model import (
    HotspotAdapterFailed,
    HotspotLifecycle,
    HotspotObserved,
    LocalControlsEvent,
    PanelButtonPressed,
    PanelDisplayState,
    PanelLink,
    PanelLinkChanged,
)
from e87canbus.local_controls.ports import LocalControlsInputSink

HOTSPOT_TRANSITION_S = 0.25


class InMemoryPanel:
    """Emulate the RP2040's complete-state refresh and local link timeout display."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._submit: LocalControlsInputSink | None = None
        self._link = PanelLink.CONNECTED
        self._desired_display = PanelDisplayState.STARTING
        self._sequence = 0

    @property
    def effective_display(self) -> PanelDisplayState:
        with self._lock:
            return (
                self._desired_display
                if self._link is PanelLink.CONNECTED
                else PanelDisplayState.FAULT
            )

    def start(self, submit: LocalControlsInputSink) -> None:
        with self._lock:
            self._submit = submit

    def set_display(self, display: PanelDisplayState) -> None:
        with self._lock:
            self._desired_display = display

    def poll(self, now: float) -> None:
        del now

    def close(self) -> None:
        with self._lock:
            self._submit = None

    def tap_button(self) -> bool:
        with self._lock:
            if self._link is PanelLink.DISCONNECTED:
                return False
            sequence = (self._sequence + 1) & 0xFFFF_FFFF
            submit = self._submit
            if submit is None or not submit(PanelButtonPressed(sequence)):
                return False
            self._sequence = sequence
            return True

    def set_link(self, link: PanelLink) -> bool:
        with self._lock:
            if link is self._link:
                return True
            submit = self._submit
            if submit is None or not submit(PanelLinkChanged(link)):
                return False
            self._link = link
            return True

    def reset(self) -> None:
        with self._lock:
            self._link = PanelLink.CONNECTED
            self._desired_display = PanelDisplayState.STARTING


class InMemoryHotspot:
    """Deterministic hotspot lifecycle driven by the service's monotonic clock."""

    def __init__(
        self,
        *,
        clock: Callable[[], float],
        transition_s: float = HOTSPOT_TRANSITION_S,
    ) -> None:
        self._clock = clock
        self._transition_s = transition_s
        self._lock = threading.Lock()
        self._submit: LocalControlsInputSink | None = None
        self._lifecycle = HotspotLifecycle.DISABLED
        self._client_connected = False
        self._deadline: float | None = None
        self._failure_enabled = False

    def start(self, submit: LocalControlsInputSink) -> None:
        with self._lock:
            self._submit = submit

    def activate(self) -> None:
        with self._lock:
            if self._failure_enabled:
                raise OSError("simulated hotspot adapter failure")
            self._lifecycle = HotspotLifecycle.ACTIVATING
            self._client_connected = False
            self._deadline = self._clock() + self._transition_s

    def deactivate(self) -> None:
        with self._lock:
            if self._failure_enabled:
                raise OSError("simulated hotspot adapter failure")
            self._lifecycle = HotspotLifecycle.DEACTIVATING
            self._client_connected = False
            self._deadline = self._clock() + self._transition_s

    def poll(self, now: float) -> None:
        with self._lock:
            if self._deadline is not None and now >= self._deadline:
                lifecycle = (
                    HotspotLifecycle.ACTIVE
                    if self._lifecycle is HotspotLifecycle.ACTIVATING
                    else HotspotLifecycle.DISABLED
                )
                submit = self._submit
                if submit is not None and submit(
                    HotspotObserved(lifecycle, self._client_connected)
                ):
                    self._lifecycle = lifecycle
                    self._deadline = None

    def close(self) -> None:
        with self._lock:
            self._submit = None

    def set_client_connected(self, connected: bool) -> bool:
        with self._lock:
            if self._lifecycle is not HotspotLifecycle.ACTIVE:
                return not connected
            submit = self._submit
            event = HotspotObserved(HotspotLifecycle.ACTIVE, connected)
            if submit is None or not submit(event):
                return False
            self._client_connected = connected
            return True

    def set_failure(self, enabled: bool) -> bool:
        with self._lock:
            if enabled:
                event: LocalControlsEvent = HotspotAdapterFailed(
                    "simulated hotspot adapter failure"
                )
            else:
                event = HotspotObserved(HotspotLifecycle.DISABLED)
            submit = self._submit
            if submit is None or not submit(event):
                return False
            self._failure_enabled = enabled
            self._lifecycle = (
                HotspotLifecycle.FAULT if enabled else HotspotLifecycle.DISABLED
            )
            self._client_connected = False
            self._deadline = None
            return True

    def reset(self) -> None:
        with self._lock:
            self._lifecycle = HotspotLifecycle.DISABLED
            self._client_connected = False
            self._deadline = None
            self._failure_enabled = False
