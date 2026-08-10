"""Every command a user can assign to a button, and nothing else.

This file is the one you edit to add an assignable command. It holds the catalogue and
the shapes that describe an entry; the behaviour derived from it - lookup, codec, the
active condition a button reports, the configuration check - lives in
:mod:`e87canbus.domain.buttons.commands` and needs no change when the catalogue grows.

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
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar, get_args

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
from e87canbus.domain.state import ApplicationState, MaximumAssistance, SteeringMode

# Every operator intent is assignable to a button, so this is an alias rather than a
# second union to keep in step. If an intent is ever added that a user must not be able
# to bind, the coverage check at the end of this file fails and the two are split then.
ButtonCommand = OperatorIntent


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


ButtonCommandActive = Callable[[ApplicationState, "ButtonCommand"], bool]

CommandT = TypeVar("CommandT")


def _bound(
    command_type: type[CommandT],
    predicate: Callable[[ApplicationState, CommandT], bool],
) -> ButtonCommandActive:
    """Widen a predicate written against one command to the union a slot can hold.

    A catalogue entry pairs its predicate with its command type, so the narrowing here
    restates a fact the entry already guarantees. It exists so each predicate can read
    its own parameters by name instead of matching over the whole union, and so the
    single mismatch check lives in one place rather than in seven predicates.
    """

    def widened(state: ApplicationState, command: ButtonCommand) -> bool:
        if not isinstance(command, command_type):
            raise TypeError(
                f"{command_type.__name__} predicate applied to {type(command).__name__}"
            )
        return predicate(state, command)

    return widened


def _current_mode(state: ApplicationState) -> SteeringMode:
    """The mode the operator is in, treating maximum assistance as manual.

    Maximum assistance is a distinct steering *state* rather than a mode value, and it
    is entered from manual and returns to it, so a mode question asked while it is
    engaged is answered as manual - the same collapse the LED derivation makes.
    """

    steering = state.steering
    return SteeringMode.MANUAL if isinstance(steering, MaximumAssistance) else steering.mode


def _maximum_assistance_active(state: ApplicationState) -> bool:
    return isinstance(state.steering, MaximumAssistance)


def _manual_level(state: ApplicationState) -> int | None:
    """The manual stage in force, or ``None`` when none is.

    Automatic and maximum assistance both retain a stage, but the car is not obeying it:
    ``_establish_manual_assistance`` cancels maximum assistance and selects manual before
    applying either stage command, so pressing a stage button in those states changes
    what the steering does. A button that changes something is not reporting a state the
    car is already in, so it is inactive.
    """

    steering = state.steering
    if isinstance(steering, MaximumAssistance) or steering.mode is not SteeringMode.MANUAL:
        return None
    return steering.manual_level


@dataclass(frozen=True)
class ButtonCommandSpec:
    """One assignable command: its wire tag, its intent, its values, and its condition.

    ``active`` is the observable condition under which a button bound to this command
    reads as on. It takes the bound command because activeness depends on the command's
    parameters and not only on its type: ``select_steering_mode(auto)`` is active in
    automatic while ``select_steering_mode(manual)`` is not. ``None`` means the command
    has no observable condition at all, which is a fact about the command rather than a
    default - a slot holding one may not carry an animation.
    """

    tag: str
    command_type: type[Any]
    fields: tuple[ButtonCommandField, ...] = ()
    # Required and keyword-only, with no default: an added command must say whether it
    # has an observable condition, rather than silently inheriting "it has none".
    active: ButtonCommandActive | None = field(kw_only=True)

    def __post_init__(self) -> None:
        if not self.tag or self.tag.strip() != self.tag:
            raise ValueError("button command tag must be non-empty trimmed text")
        if not isinstance(self.command_type, type):
            raise TypeError("button command type must be a class")
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
        (
            ButtonCommandField(
                "mode",
                annotation=Literal["auto", "manual"],
                decode=_decode_steering_mode,
                encode=_encode_steering_mode,
            ),
        ),
        active=_bound(
            SelectSteeringMode,
            lambda state, command: _current_mode(state) is command.mode,
        ),
    ),
    ButtonCommandSpec(
        "toggle_automatic_assistance",
        ToggleAutomaticAssistance,
        active=_bound(
            ToggleAutomaticAssistance,
            lambda state, _command: _current_mode(state) is SteeringMode.AUTO,
        ),
    ),
    ButtonCommandSpec(
        "adjust_manual_assistance",
        AdjustManualAssistance,
        (ButtonCommandField("delta", annotation=Literal[-1, 1]),),
        # A relative step has no state it can be "in"; the level it moves reports itself.
        active=None,
    ),
    ButtonCommandSpec(
        "set_manual_assistance_level",
        SetManualAssistanceLevel,
        (ButtonCommandField("level", minimum=0),),
        active=_bound(
            SetManualAssistanceLevel,
            lambda state, command: _manual_level(state) == command.level,
        ),
    ),
    ButtonCommandSpec(
        "set_maximum_assistance",
        SetMaximumAssistance,
        (ButtonCommandField("enabled", annotation=bool),),
        active=_bound(
            SetMaximumAssistance,
            lambda state, command: _maximum_assistance_active(state) is command.enabled,
        ),
    ),
    ButtonCommandSpec(
        "toggle_maximum_assistance",
        ToggleMaximumAssistance,
        active=_bound(
            ToggleMaximumAssistance,
            lambda state, _command: _maximum_assistance_active(state),
        ),
    ),
    ButtonCommandSpec(
        "start_high_beam_strobe",
        StartHighBeamStrobe,
        # Lighting while the strobe runs needs a running flag the derivation can read,
        # which does not exist yet; until it does the strobe has no observable condition.
        active=None,
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
