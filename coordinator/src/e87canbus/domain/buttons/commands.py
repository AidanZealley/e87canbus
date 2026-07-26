"""Behaviour derived from the button-command catalogue.

Everything here reads :mod:`e87canbus.domain.buttons.catalogue` and needs no change when
a command is added: lookup, the storage and wire codec, the condition under which a
bound command's button reads as active, and the check for values a particular vehicle
configuration cannot run.
"""

from __future__ import annotations

from typing import Any, TypeGuard, assert_never

from e87canbus.config import SteeringConfig
from e87canbus.domain.buttons.catalogue import (
    SPECS_BY_TAG,
    SPECS_BY_TYPE,
    ButtonCommand,
    ButtonCommandSpec,
)
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    StartHighBeamStrobe,
    ToggleAutomaticAssistance,
    ToggleMaximumAssistance,
)
from e87canbus.domain.state import ApplicationState

_BUTTON_COMMAND_TYPES = tuple(SPECS_BY_TYPE)


def is_button_command(value: object) -> TypeGuard[ButtonCommand]:
    return isinstance(value, _BUTTON_COMMAND_TYPES)


def _spec_for(command: ButtonCommand) -> ButtonCommandSpec:
    try:
        return SPECS_BY_TYPE[type(command)]
    except KeyError as exc:
        raise TypeError(f"unsupported button command: {type(command).__name__}") from exc


def button_command_has_active_state(command: ButtonCommand) -> bool:
    """Whether this command has an observable condition its button can report.

    Authored animation renders the active state alone, so a command that can never be
    active has nothing to animate and a slot may not carry one for it.
    """

    return _spec_for(command).active is not None


def button_command_is_active(state: ApplicationState, command: ButtonCommand) -> bool:
    """Whether the bound command's condition holds right now; ``False`` if it has none."""

    predicate = _spec_for(command).active
    return predicate is not None and predicate(state, command)


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
    spec = SPECS_BY_TAG.get(tag)
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
