"""Pure hardware-independent application decisions.

The controller is split by concern: ``button_leds`` (LED projection),
``steering`` (assistance-command math), ``snapshot`` (the read-only projection),
``reducer`` (event -> next state) and ``intents`` (operator intent -> next state).
Import the public surface from this package; the split is an internal layout.
"""

from e87canbus.domain.controller.button_leds import (
    DEMO_BREATHE_BUTTON_INDEX,
    MAXIMUM_ASSISTANCE_BUTTON_INDEX,
    SOFT_AMBER,
    SOFT_WHITE,
    STEERING_MODE_BUTTON_INDEX,
    button_led_effect,
    button_led_state,
    button_pad_program,
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
    "DEMO_BREATHE_BUTTON_INDEX",
    "MAXIMUM_ASSISTANCE_BUTTON_INDEX",
    "SOFT_AMBER",
    "SOFT_WHITE",
    "STEERING_MODE_BUTTON_INDEX",
    "ApplicationSnapshot",
    "EngineTelemetrySnapshot",
    "EngineTelemetryStatus",
    "EngineTelemetryValue",
    "Transition",
    "button_led_effect",
    "button_led_state",
    "button_pad_program",
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
