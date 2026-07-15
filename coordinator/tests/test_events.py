import pytest
from e87canbus.application.events import (
    ButtonLedState,
    HighBeamStrobeDeadlineReached,
    LedColour,
    SetHighBeam,
    SetSteeringAssistance,
    SteeringCommandReason,
)
from e87canbus.config import HighBeamStrobeConfig


def test_steering_effect_rejects_out_of_range_assistance() -> None:
    with pytest.raises(ValueError, match="between zero and one"):
        SetSteeringAssistance(1.1, SteeringCommandReason.MAXIMUM)


def test_button_led_state_rejects_partial_and_unknown_colours() -> None:
    with pytest.raises(ValueError, match="exactly 16"):
        ButtonLedState((LedColour.OFF,) * 15)
    with pytest.raises(ValueError, match="known LED colours"):
        ButtonLedState((LedColour.OFF,) * 15 + ("off",))  # type: ignore[arg-type]


def test_high_beam_effect_requires_boolean() -> None:
    with pytest.raises(ValueError, match="must be a boolean"):
        SetHighBeam(1)  # type: ignore[arg-type]


@pytest.mark.parametrize("now", (float("inf"), float("-inf"), float("nan")))
def test_high_beam_strobe_deadline_requires_finite_timestamp(now: float) -> None:
    with pytest.raises(ValueError, match="deadline must be finite"):
        HighBeamStrobeDeadlineReached(now)


@pytest.mark.parametrize(
    "kwargs",
    (
        {"button_index": -1},
        {"button_index": True},
        {"cycle_count": 0},
        {"cycle_count": False},
        {"asserted_duration_s": 0.0},
        {"deasserted_duration_s": float("inf")},
    ),
)
def test_high_beam_strobe_config_rejects_invalid_plans(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        HighBeamStrobeConfig(**kwargs)  # type: ignore[arg-type]
