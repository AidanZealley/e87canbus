"""Button-pad bindings expressed as replaceable operator-intent profiles."""

from __future__ import annotations

from dataclasses import dataclass

from e87canbus.config import BUILT_IN_RESERVED_BUTTON_INDEXES, HighBeamStrobeConfig
from e87canbus.domain.events import BUTTON_LED_COUNT
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    OperatorIntent,
    StartHighBeamStrobe,
    ToggleAutomaticAssistance,
    ToggleButtonPadDemoBreathe,
    ToggleMaximumAssistance,
    is_operator_intent,
)

BUILT_IN_PROFILE_ID = "built-in"


@dataclass(frozen=True)
class ButtonBinding:
    button_index: int
    press_intent: OperatorIntent

    def __post_init__(self) -> None:
        if type(self.button_index) is not int or not 0 <= self.button_index < BUTTON_LED_COUNT:
            raise ValueError(f"button_index must be between 0 and {BUTTON_LED_COUNT - 1}")
        if not is_operator_intent(self.press_intent):
            raise TypeError("press_intent must be a supported operator intent")


@dataclass(frozen=True)
class ButtonBindingProfile:
    """A validated, immutable mapping from button presses to operator intents."""

    profile_id: str
    bindings: tuple[ButtonBinding, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str):
            raise TypeError("profile_id must be a string")
        if not self.profile_id or self.profile_id.strip() != self.profile_id:
            raise ValueError("profile_id must be a non-empty trimmed string")
        if not isinstance(self.bindings, tuple):
            raise TypeError("bindings must be an immutable tuple")
        if any(not isinstance(binding, ButtonBinding) for binding in self.bindings):
            raise TypeError("bindings must contain only ButtonBinding values")
        indexes = tuple(binding.button_index for binding in self.bindings)
        if len(indexes) != len(set(indexes)):
            raise ValueError("a button profile cannot bind the same button more than once")

    def intent_for_press(self, button_index: int) -> OperatorIntent | None:
        if type(button_index) is not int or not 0 <= button_index < BUTTON_LED_COUNT:
            raise ValueError(f"button_index must be between 0 and {BUTTON_LED_COUNT - 1}")
        return next(
            (
                binding.press_intent
                for binding in self.bindings
                if binding.button_index == button_index
            ),
            None,
        )


# The built-in profile's fixed (non-high-beam) button bindings. Their indexes are
# owned by config.BUILT_IN_RESERVED_BUTTON_INDEXES so a HighBeamStrobeConfig can never
# be placed on one of them; the two definitions are checked for agreement below so
# neither can drift without failing loudly at import time.
_BUILT_IN_FIXED_BINDINGS: tuple[ButtonBinding, ...] = (
    ButtonBinding(0, ToggleAutomaticAssistance()),
    ButtonBinding(1, AdjustManualAssistance(-1)),
    ButtonBinding(2, AdjustManualAssistance(1)),
    ButtonBinding(3, ToggleMaximumAssistance()),
    ButtonBinding(15, ToggleButtonPadDemoBreathe()),
)

if (
    frozenset(binding.button_index for binding in _BUILT_IN_FIXED_BINDINGS)
    != BUILT_IN_RESERVED_BUTTON_INDEXES
):
    raise RuntimeError(
        "built-in fixed button bindings must match config.BUILT_IN_RESERVED_BUTTON_INDEXES"
    )


def built_in_button_binding_profile(
    high_beam_strobe_config: HighBeamStrobeConfig | None = None,
) -> ButtonBindingProfile:
    """Return the current compiled-in pad mapping as a replaceable profile."""

    high_beam_button_index = (high_beam_strobe_config or HighBeamStrobeConfig()).button_index
    return ButtonBindingProfile(
        profile_id=BUILT_IN_PROFILE_ID,
        bindings=(
            *_BUILT_IN_FIXED_BINDINGS,
            ButtonBinding(high_beam_button_index, StartHighBeamStrobe()),
        ),
    )
