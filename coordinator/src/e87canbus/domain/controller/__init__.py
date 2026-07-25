"""The decision layer: pure functions from state plus an input to state plus effects.

Where the rest of ``domain`` defines what things *are*, this package decides what
should *happen*. Nothing here holds state - the caller (the kernel) owns it and passes
it in, so every function can be tested by calling it with a state value and comparing
the result. "Effects" are inert descriptions of work, never performed here.

    reducer      an observed, timer or failure event -> next state
    intents      an operator intent -> next state, plus press feedback
    snapshot     current state -> the immutable read-only projection clients see
    button_leds  current state + the active button profile -> the pad's LED program
    steering     current state + the active curve -> the assistance command to send

The first two answer "what changed", the last three "what should now be displayed or
transmitted". Several of these are the verb half of a feature whose noun half lives in
the vocabulary layer: ``button_leds`` pairs with ``domain.buttons``, ``steering`` with
``domain.steering``. That layering is deliberate and one-directional - see the
``domain`` package docstring.

Import the public surface from this package; the module split is internal layout.
"""

from e87canbus.domain.controller.button_leds import (
    SOFT_AMBER,
    SOFT_WHITE,
    ButtonLedPresenter,
    ButtonLedProjection,
    derived_button_led_state,
)
from e87canbus.domain.controller.intents import (
    clear_maximum_assistance,
    execute_operator_intent,
    finish_button_intent,
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
    "SOFT_AMBER",
    "SOFT_WHITE",
    "ApplicationSnapshot",
    "ButtonLedPresenter",
    "ButtonLedProjection",
    "EngineTelemetrySnapshot",
    "EngineTelemetryStatus",
    "EngineTelemetryValue",
    "Transition",
    "derived_button_led_state",
    "clear_maximum_assistance",
    "execute_operator_intent",
    "finish_button_intent",
    "initial_effects",
    "normalize_state",
    "snapshot",
    "steering_command_for_active_curve",
    "steering_command_for_current_state",
    "transition",
]
