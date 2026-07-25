"""The declarative command catalogue assignable to button-pad slots."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeGuard, get_args

from e87canbus.domain.intents import (
    AdjustManualAssistance,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    StartHighBeamStrobe,
    ToggleAutomaticAssistance,
    ToggleMaximumAssistance,
)
from e87canbus.domain.state import SteeringMode

ButtonCommand = (
    SelectSteeringMode
    | ToggleAutomaticAssistance
    | AdjustManualAssistance
    | SetManualAssistanceLevel
    | SetMaximumAssistance
    | ToggleMaximumAssistance
    | StartHighBeamStrobe
)


class ButtonCommandPresentation(Enum):
    STEERING_MODE = "steering_mode"
    STEERING_ADJUSTMENT = "steering_adjustment"
    MAXIMUM_ASSISTANCE = "maximum_assistance"
    MOMENTARY = "momentary"


def _identity(value: Any) -> Any:
    return value


@dataclass(frozen=True)
class ButtonCommandField:
    name: str
    decode: Callable[[Any], Any] = _identity
    encode: Callable[[Any], Any] = _identity

    def __post_init__(self) -> None:
        if not self.name or self.name.strip() != self.name:
            raise ValueError("button command field name must be non-empty trimmed text")


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
        (ButtonCommandField("delta"),),
    ),
    ButtonCommandSpec(
        "set_manual_assistance_level",
        SetManualAssistanceLevel,
        ButtonCommandPresentation.STEERING_ADJUSTMENT,
        (ButtonCommandField("level"),),
    ),
    ButtonCommandSpec(
        "set_maximum_assistance",
        SetMaximumAssistance,
        ButtonCommandPresentation.MAXIMUM_ASSISTANCE,
        (ButtonCommandField("enabled"),),
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
if set(_SPECS_BY_TYPE) != set(get_args(ButtonCommand)):
    raise RuntimeError("button command catalogue must cover the complete ButtonCommand union")

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
        **{
            field.name: field.encode(getattr(command, field.name))
            for field in spec.fields
        },
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
