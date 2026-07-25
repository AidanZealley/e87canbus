"""The declarative command catalogue assignable to button-pad slots.

Adding an assignable command is three edits and no more:

1. an intent dataclass in :mod:`e87canbus.domain.intents`, added to ``OperatorIntent``
2. a :class:`ButtonCommandSpec` in ``BUTTON_COMMAND_CATALOGUE`` below
3. the behaviour, as a match arm in ``domain.controller.intents._apply_operator_intent``

Everything else - the storage codec, the HTTP schema, LED presentation and the
configuration check - is derived from the catalogue or is an exhaustive match that
fails type-checking until the new command is handled.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, TypeGuard, assert_never, get_args

from e87canbus.config import SteeringConfig
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
# to bind, the catalogue-coverage check below fails and the two are split then.
ButtonCommand = OperatorIntent


class ButtonCommandPresentation(Enum):
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


# Adding an assignable command means adding one specification here. Generic lookup,
# validation and codecs below derive their behaviour from this immutable catalogue.
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

_SPECS_BY_TAG = {spec.tag: spec for spec in BUTTON_COMMAND_CATALOGUE}
_SPECS_BY_TYPE = {spec.command_type: spec for spec in BUTTON_COMMAND_CATALOGUE}
if len(_SPECS_BY_TAG) != len(BUTTON_COMMAND_CATALOGUE):
    raise RuntimeError("button command catalogue contains duplicate tags")
if len(_SPECS_BY_TYPE) != len(BUTTON_COMMAND_CATALOGUE):
    raise RuntimeError("button command catalogue contains duplicate command types")
if set(_SPECS_BY_TYPE) != set(get_args(OperatorIntent)):
    raise RuntimeError("button command catalogue must cover every operator intent exactly")

_BUTTON_COMMAND_TYPES = tuple(_SPECS_BY_TYPE)


def is_button_command(value: object) -> TypeGuard[ButtonCommand]:
    return isinstance(value, _BUTTON_COMMAND_TYPES)


def _spec_for(command: ButtonCommand) -> ButtonCommandSpec:
    try:
        return _SPECS_BY_TYPE[type(command)]
    except KeyError as exc:
        raise TypeError(f"unsupported button command: {type(command).__name__}") from exc


def button_command_presentation(command: ButtonCommand) -> ButtonCommandPresentation:
    """Return steady LED semantics from the command's catalogue entry."""

    return _spec_for(command).presentation


def encode_button_command(command: ButtonCommand) -> dict[str, Any]:
    """Encode one command for both durable storage and the HTTP boundary."""

    spec = _spec_for(command)
    return {
        "type": spec.tag,
        **{field.name: field.encode(getattr(command, field.name)) for field in spec.fields},
    }


def decode_button_command(value: object) -> ButtonCommand:
    """Decode one strict tagged command using its catalogue specification."""

    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        raise ValueError("command must be a tagged object")
    tag = value["type"]
    spec = _SPECS_BY_TAG.get(tag)
    expected_fields = {"type"} if spec is None else {"type", *(field.name for field in spec.fields)}
    if spec is None or set(value) != expected_fields:
        raise ValueError(f"unsupported or malformed button command: {tag}")
    command = spec.command_type(
        **{field.name: field.decode(value[field.name]) for field in spec.fields}
    )
    if not is_button_command(command):
        raise TypeError(f"catalogue constructed an unsupported button command: {tag}")
    return command


def button_command_configuration_error(
    command: ButtonCommand,
    steering_config: SteeringConfig,
) -> str | None:
    """Explain why a command cannot run under this configuration, or ``None`` if it can.

    Some commands carry a value whose legal range is a property of the vehicle rather
    than of the schema - an assistance stage only exists if the steering configuration
    defines it. Those bounds cannot be expressed in the stored definition, so they are
    checked here: at the save boundary, so an unusable profile is never stored, and
    again on press, so a profile stored before a configuration change fails as button
    feedback instead of as an exception.
    """

    match command:
        case SetManualAssistanceLevel(level=level):
            if not 0 <= level < steering_config.manual_level_count:
                return (
                    f"manual assistance level must be between 0 and "
                    f"{steering_config.manual_level_count - 1}"
                )
            return None
        case (
            SelectSteeringMode()
            | ToggleAutomaticAssistance()
            | AdjustManualAssistance()
            | SetMaximumAssistance()
            | ToggleMaximumAssistance()
            | StartHighBeamStrobe()
        ):
            return None
        case _:
            assert_never(command)
