"""The decision layer: pure functions from state plus an input to state plus effects.

Where the rest of ``domain`` defines what things *are*, this package decides what
should *happen*. Nothing here holds state - the caller (the kernel) owns it and passes
it in, so every function can be tested by calling it with a state value and comparing
the result. "Effects" are inert descriptions of work, never performed here.

    reducer      an observed, timer or failure event -> next state
    intents      an operator or button intent -> desired state
    snapshot     current state -> the immutable read-only projection clients see
    steering     current state + the active curve -> the assistance command to send

The first two answer "what changed". The snapshot and steering projection
answer what should be published or sent. See the ``domain`` package docstring
for the one-way dependency rule.

Import the public surface from this package; the module split is internal layout.
"""

from e87canbus.domain.controller.intents import (
    clear_maximum_assistance,
    execute_operator_intent,
)
from e87canbus.domain.controller.reducer import (
    Transition,
    normalize_state,
    transition,
)
from e87canbus.domain.controller.snapshot import (
    ApplicationSnapshot,
    EngineTelemetrySnapshot,
    EngineTelemetryStatus,
    EngineTelemetryValue,
    initial_effects,
    snapshot,
)
from e87canbus.domain.controller.steering import (
    steering_command_for_active_curve,
    steering_command_for_current_state,
)

__all__ = [
    "ApplicationSnapshot",
    "EngineTelemetrySnapshot",
    "EngineTelemetryStatus",
    "EngineTelemetryValue",
    "Transition",
    "clear_maximum_assistance",
    "execute_operator_intent",
    "initial_effects",
    "normalize_state",
    "snapshot",
    "steering_command_for_active_curve",
    "steering_command_for_current_state",
    "transition",
]
