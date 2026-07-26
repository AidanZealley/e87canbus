"""Immutable domain state values."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

from e87canbus.config import CanNetwork


class SteeringMode(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


Rgb = tuple[int, int, int]
RGB_OFF: Rgb = (0, 0, 0)
RGB_RED: Rgb = (255, 0, 0)
RGB_BLUE: Rgb = (0, 0, 255)
RGB_AMBER: Rgb = (255, 191, 0)
RGB_WHITE: Rgb = (255, 255, 255)


@dataclass(frozen=True)
class ButtonFeedback:
    """A transient press-feedback blink, resolved to what the pad should show.

    Feedback used to be a closed enum of three system colours. Authored button
    colours make the acknowledgement flash carry the slot's own colour, which no
    enum can name, so the colour is resolved in the domain and the frame carries
    it verbatim.
    """

    rgb: Rgb
    pulses: int

    def __post_init__(self) -> None:
        if len(self.rgb) != 3 or any(
            type(channel) is not int or not 0 <= channel <= 0xFF for channel in self.rgb
        ):
            raise ValueError("button feedback colour must be RGB bytes")
        # Feedback reaches the pad two ways — the low-latency 0x701 frame and the
        # blink track composed into the ISO-TP program — and the pad implements only
        # one- and two-pulse blinks. Bounding it here keeps both paths agreeing on
        # what a renderable feedback value is.
        if type(self.pulses) is not int or self.pulses not in (1, 2):
            raise ValueError("button feedback pulses must be one or two")


BUTTON_FEEDBACK_REJECTED = ButtonFeedback(RGB_RED, 2)
BUTTON_FEEDBACK_UNAVAILABLE = ButtonFeedback(RGB_AMBER, 2)
BUTTON_FEEDBACK_UNBOUND = ButtonFeedback(RGB_WHITE, 1)


@dataclass(frozen=True)
class NormalSteering:
    mode: SteeringMode = SteeringMode.AUTO
    manual_level: int = 0


@dataclass(frozen=True)
class MaximumAssistance:
    previous: NormalSteering


SteeringState = NormalSteering | MaximumAssistance


@dataclass(frozen=True)
class SpeedSample:
    speed_kph: float
    observed_at: float
    source_network: CanNetwork


@dataclass(frozen=True)
class EngineRpmSample:
    rpm: int
    observed_at: float
    source_network: CanNetwork


@dataclass(frozen=True)
class OilTemperatureSample:
    temperature_c: float
    observed_at: float
    source_network: CanNetwork


@dataclass(frozen=True)
class CoolantTemperatureSample:
    temperature_c: float
    observed_at: float
    source_network: CanNetwork


@dataclass(frozen=True)
class ApplicationState:
    steering: SteeringState = field(default_factory=NormalSteering)
    speed_sample: SpeedSample | None = None
    speed_evaluated_at: float = 0.0
    engine_rpm_sample: EngineRpmSample | None = None
    oil_temperature_sample: OilTemperatureSample | None = None
    coolant_temperature_sample: CoolantTemperatureSample | None = None
    engine_telemetry_evaluated_at: float = 0.0
    high_beam_enabled: bool = False
    high_beam_strobe_cycles_remaining: int = 0
    high_beam_next_transition_at: float | None = None
    button_feedback_deadlines: tuple[float | None, ...] = (None,) * 16
    button_feedback: tuple[ButtonFeedback | None, ...] = (None,) * 16

    def __post_init__(self) -> None:
        if len(self.button_feedback_deadlines) != 16:
            raise ValueError("button feedback deadlines must contain exactly 16 entries")
        if len(self.button_feedback) != 16:
            raise ValueError("button feedback must contain exactly 16 entries")
        for deadline in self.button_feedback_deadlines:
            if deadline is not None and not math.isfinite(deadline):
                raise ValueError("button feedback deadlines must be finite")
        if any(
            feedback is not None and not isinstance(feedback, ButtonFeedback)
            for feedback in self.button_feedback
        ):
            raise ValueError("button feedback must contain ButtonFeedback values")
