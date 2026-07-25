"""Every command a user can assign to a button, and nothing else.

This file is the one you edit to add an assignable command. It holds the catalogue and
the shapes that describe an entry; the behaviour derived from it - lookup, codec, LED
presentation, the configuration check - lives in :mod:`e87canbus.domain.buttons.commands`
and needs no change when the catalogue grows.

Adding a command is two edits here and in :mod:`e87canbus.domain.intents`, after which
type checking names every remaining decision:

1. an intent dataclass in ``intents``, added to the ``OperatorIntent`` union
2. a :class:`ButtonCommandSpec` in ``BUTTON_COMMAND_CATALOGUE`` below

``mypy`` then fails on each exhaustive match that has not yet handled it - whether the
command needs Servotronic, whether it has a configuration-dependent bound, and what it
actually does - so nothing can half-land.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, get_args

from e87canbus.domain.intents import (
    AdjustManualAssistance,
    OperatorIntent,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    StartHighBeamStrobe,
    ToggleAutomaticAssistance,
    ToggleMaximumAssistance,
)
from e87canbus.domain.state import SteeringMode

# Every operator intent is assignable to a button, so this is an alias rather than a
# second union to keep in step. If an intent is ever added that a user must not be able
# to bind, the coverage check at the end of this file fails and the two are split then.
ButtonCommand = OperatorIntent


class ButtonCommandPresentation(Enum):
    """How a command's button looks when idle, independent of which button it is on."""

    STEERING_MODE = "steering_mode"
    STEERING_ADJUSTMENT = "steering_adjustment"
    MAXIMUM_ASSISTANCE = "maximum_assistance"
    MOMENTARY = "momentary"


def _identity(value: Any) -> Any:
    return value


@dataclass(frozen=True)
class ButtonCommandField:
    """One value a command carries, described once for storage and for the wire.

    ``annotation`` is the field's JSON-side type and ``minimum`` its lower bound, and
    the HTTP request models are generated from the pair. They describe the shape a
    client may send, using only builtins and ``typing`` so the catalogue stays free of
    any serialisation library; the intent dataclass remains the authority on what is
    ultimately legal, so a looser annotation fails at construction rather than
    reaching the runtime.
    """

    name: str
    annotation: Any = int
    minimum: int | None = None
    decode: Callable[[Any], Any] = _identity
    encode: Callable[[Any], Any] = _identity

    def __post_init__(self) -> None:
        if not self.name or self.name.strip() != self.name:
            raise ValueError("button command field name must be non-empty trimmed text")
        if self.minimum is not None and self.annotation is not int:
            raise ValueError("only an integer button command field may declare a minimum")


@dataclass(frozen=True)
class ButtonCommandSpec:
    """One assignable command: its wire tag, its intent, its look, and its values."""

    tag: str
    command_type: type[Any]
    presentation: ButtonCommandPresentation
    fields: tuple[ButtonCommandField, ...] = ()

    def __post_init__(self) -> None:
        if not self.tag or self.tag.strip() != self.tag:
            raise ValueError("button command tag must be non-empty trimmed text")
        if not isinstance(self.command_type, type):
            raise TypeError("button command type must be a class")
        if not isinstance(self.presentation, ButtonCommandPresentation):
            raise TypeError("button command presentation must be supported")
        names = tuple(field.name for field in self.fields)
        if len(names) != len(set(names)):
            raise ValueError(f"button command {self.tag} has duplicate fields")


def _decode_steering_mode(value: Any) -> SteeringMode:
    return SteeringMode(value)


def _encode_steering_mode(value: Any) -> str:
    if not isinstance(value, SteeringMode):
        raise TypeError("steering mode command contains an invalid mode")
    return value.value


BUTTON_COMMAND_CATALOGUE: tuple[ButtonCommandSpec, ...] = (
    ButtonCommandSpec(
        "select_steering_mode",
        SelectSteeringMode,
        ButtonCommandPresentation.STEERING_MODE,
        (
            ButtonCommandField(
                "mode",
                annotation=Literal["auto", "manual"],
                decode=_decode_steering_mode,
                encode=_encode_steering_mode,
            ),
        ),
    ),
    ButtonCommandSpec(
        "toggle_automatic_assistance",
        ToggleAutomaticAssistance,
        ButtonCommandPresentation.STEERING_MODE,
    ),
    ButtonCommandSpec(
        "adjust_manual_assistance",
        AdjustManualAssistance,
        ButtonCommandPresentation.STEERING_ADJUSTMENT,
        (ButtonCommandField("delta", annotation=Literal[-1, 1]),),
    ),
    ButtonCommandSpec(
        "set_manual_assistance_level",
        SetManualAssistanceLevel,
        ButtonCommandPresentation.STEERING_ADJUSTMENT,
        (ButtonCommandField("level", minimum=0),),
    ),
    ButtonCommandSpec(
        "set_maximum_assistance",
        SetMaximumAssistance,
        ButtonCommandPresentation.MAXIMUM_ASSISTANCE,
        (ButtonCommandField("enabled", annotation=bool),),
    ),
    ButtonCommandSpec(
        "toggle_maximum_assistance",
        ToggleMaximumAssistance,
        ButtonCommandPresentation.MAXIMUM_ASSISTANCE,
    ),
    ButtonCommandSpec(
        "start_high_beam_strobe",
        StartHighBeamStrobe,
        ButtonCommandPresentation.MOMENTARY,
    ),
)

SPECS_BY_TAG = {spec.tag: spec for spec in BUTTON_COMMAND_CATALOGUE}
SPECS_BY_TYPE = {spec.command_type: spec for spec in BUTTON_COMMAND_CATALOGUE}
if len(SPECS_BY_TAG) != len(BUTTON_COMMAND_CATALOGUE):
    raise RuntimeError("button command catalogue contains duplicate tags")
if len(SPECS_BY_TYPE) != len(BUTTON_COMMAND_CATALOGUE):
    raise RuntimeError("button command catalogue contains duplicate command types")
if set(SPECS_BY_TYPE) != set(get_args(OperatorIntent)):
    raise RuntimeError("button command catalogue must cover every operator intent exactly")
