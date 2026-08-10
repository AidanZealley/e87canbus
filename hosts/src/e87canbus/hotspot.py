"""Shared hotspot behaviour for the coordinator panel."""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Protocol

LOGGER = logging.getLogger(__name__)


class HotspotObservation(StrEnum):
    DISABLED = "disabled"
    STARTING = "starting"
    WAITING = "waiting"
    CONNECTED = "connected"
    STOPPING = "stopping"


class HotspotStatus(StrEnum):
    DISABLED = "disabled"
    STARTING = "starting"
    WAITING = "waiting"
    CONNECTED = "connected"
    STOPPING = "stopping"
    FAILED = "failed"


class HotspotBackend(Protocol):
    def activate(self) -> None: ...

    def deactivate(self) -> None: ...

    def observe(self) -> HotspotObservation: ...


class HotspotService:
    """Own the button transition table around one fixed hotspot backend."""

    def __init__(self, backend: HotspotBackend) -> None:
        self._backend = backend
        self._failed_from: HotspotObservation | None = None

    def status(self) -> HotspotStatus:
        _, status = self._observe()
        return status

    def _observe(self) -> tuple[HotspotObservation | None, HotspotStatus]:
        try:
            observation = self._backend.observe()
        except Exception:
            # A backend that cannot be read is shown as failed, and a press still retries.
            # This needs no latch: the next successful observation is the recovery.
            LOGGER.exception("failed to observe coordinator hotspot")
            return None, HotspotStatus.FAILED
        if self._failed_from is not None:
            if observation == self._failed_from:
                return observation, HotspotStatus.FAILED
            self._failed_from = None
        return observation, HotspotStatus(observation.value)

    def toggle(self) -> None:
        observation, status = self._observe()

        if status is HotspotStatus.STOPPING:
            return

        activate = status in {HotspotStatus.DISABLED, HotspotStatus.FAILED}
        try:
            if activate:
                self._backend.activate()
            else:
                self._backend.deactivate()
        except Exception:
            self._failed_from = observation
            action = "activate" if activate else "deactivate"
            LOGGER.exception("failed to %s coordinator hotspot", action)
        else:
            self._failed_from = None
