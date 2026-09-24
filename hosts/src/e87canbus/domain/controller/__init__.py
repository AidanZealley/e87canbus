"""Pure desired-state transitions and browser projection."""

from e87canbus.domain.controller.intents import execute_operator_intent
from e87canbus.domain.controller.reducer import normalize_state, transition
from e87canbus.domain.controller.snapshot import (
    ApplicationSnapshot,
    EngineTelemetrySnapshot,
    EngineTelemetryStatus,
    EngineTelemetryValue,
    snapshot,
)

__all__ = [
    "execute_operator_intent",
    "normalize_state",
    "transition",
    "ApplicationSnapshot",
    "EngineTelemetrySnapshot",
    "EngineTelemetryStatus",
    "EngineTelemetryValue",
    "snapshot",
]
