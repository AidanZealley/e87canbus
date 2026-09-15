"""Platform-independent coordinator panel status."""

from __future__ import annotations

from enum import StrEnum


class CoordinatorStatus(StrEnum):
    STARTING = "starting"
    READY = "ready"
    FAULT = "fault"
    OFF = "off"
