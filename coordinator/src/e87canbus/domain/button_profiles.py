"""Durable, user-authored button-pad profile values and their storage codec."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, assert_never
from uuid import UUID

from e87canbus.domain.events import BUTTON_LED_COUNT
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    StartHighBeamStrobe,
    ToggleAutomaticAssistance,
    ToggleMaximumAssistance,
)
from e87canbus.domain.revisioned_profiles import (
    validate_saved_profile_revision as validate_saved_profile_revision,
)
from e87canbus.domain.state import SteeringMode
from e87canbus.domain.timestamps import validate_canonical_utc_timestamp

BUTTON_PROFILE_SCHEMA_VERSION = 1
BUTTON_PROFILE_NAME_MAX_LENGTH = 100
UserButtonIntent = (
    SelectSteeringMode
    | ToggleAutomaticAssistance
    | AdjustManualAssistance
    | SetManualAssistanceLevel
    | SetMaximumAssistance
    | ToggleMaximumAssistance
    | StartHighBeamStrobe
)


@dataclass(frozen=True)
class ButtonProfileDefinition:
    schema_version: int
    slots: tuple[UserButtonIntent | None, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int:
            raise ValueError("schema_version must be an integer")
        if self.schema_version != BUTTON_PROFILE_SCHEMA_VERSION:
            raise ValueError(f"unsupported button profile schema_version: {self.schema_version}")
        if not isinstance(self.slots, tuple) or len(self.slots) != BUTTON_LED_COUNT:
            raise ValueError(f"slots must be an immutable {BUTTON_LED_COUNT}-entry tuple")
        if any(value is not None and not is_user_button_intent(value) for value in self.slots):
            raise ValueError("slots contain an intent that is not user-bindable")


@dataclass(frozen=True)
class StoredButtonProfile:
    profile_id: str
    name: str
    revision: int
    definition: ButtonProfileDefinition
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        validate_button_profile_id(self.profile_id)
        validate_button_profile_name(self.name)
        if self.revision is None:
            raise ValueError("profile revision must be a positive integer")
        validate_saved_profile_revision(self.revision, "profile revision")
        if not isinstance(self.definition, ButtonProfileDefinition):
            raise ValueError("definition must be a ButtonProfileDefinition")
        validate_canonical_utc_timestamp(self.created_at, "created_at")
        validate_canonical_utc_timestamp(self.updated_at, "updated_at")


def is_user_button_intent(value: object) -> bool:
    return isinstance(
        value,
        (
            SelectSteeringMode,
            ToggleAutomaticAssistance,
            AdjustManualAssistance,
            SetManualAssistanceLevel,
            SetMaximumAssistance,
            ToggleMaximumAssistance,
            StartHighBeamStrobe,
        ),
    )


def empty_button_profile_definition() -> ButtonProfileDefinition:
    return ButtonProfileDefinition(BUTTON_PROFILE_SCHEMA_VERSION, (None,) * BUTTON_LED_COUNT)


BUILT_IN_BUTTON_PROFILE = ButtonProfileDefinition(
    BUTTON_PROFILE_SCHEMA_VERSION,
    (
        ToggleAutomaticAssistance(),
        AdjustManualAssistance(-1),
        AdjustManualAssistance(1),
        ToggleMaximumAssistance(),
        StartHighBeamStrobe(),
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    ),
)


def validate_button_profile_name(name: str) -> None:
    if not isinstance(name, str) or not name or name != name.strip():
        raise ValueError("profile name must be non-empty trimmed text")
    if len(name) > BUTTON_PROFILE_NAME_MAX_LENGTH:
        raise ValueError(
            f"profile name must contain at most {BUTTON_PROFILE_NAME_MAX_LENGTH} characters"
        )


def validate_button_profile_id(profile_id: str) -> None:
    if not isinstance(profile_id, str):
        raise ValueError("profile_id must be UUID text")
    try:
        canonical = str(UUID(profile_id))
    except (ValueError, AttributeError) as error:
        raise ValueError("profile_id must be UUID text") from error
    if canonical != profile_id:
        raise ValueError("profile_id must use canonical UUID text")


def encode_button_intent(intent: UserButtonIntent) -> dict[str, Any]:
    """Tag one bindable intent for the wire and for storage.

    This is the only encoder: the HTTP layer serialises responses through it too, so a
    new command can never be persisted in one shape and published in another.
    """

    match intent:
        case SelectSteeringMode(mode=mode):
            return {"type": "select_steering_mode", "mode": mode.value}
        case ToggleAutomaticAssistance():
            return {"type": "toggle_automatic_assistance"}
        case AdjustManualAssistance(delta=delta):
            return {"type": "adjust_manual_assistance", "delta": delta}
        case SetManualAssistanceLevel(level=level):
            return {"type": "set_manual_assistance_level", "level": level}
        case SetMaximumAssistance(enabled=enabled):
            return {"type": "set_maximum_assistance", "enabled": enabled}
        case ToggleMaximumAssistance():
            return {"type": "toggle_maximum_assistance"}
        case StartHighBeamStrobe():
            return {"type": "start_high_beam_strobe"}
        case _:
            assert_never(intent)


def canonical_button_profile_bytes(definition: ButtonProfileDefinition) -> bytes:
    value = {
        "schema_version": definition.schema_version,
        "slots": [
            None if intent is None else encode_button_intent(intent) for intent in definition.slots
        ],
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def decode_button_profile(value: object) -> ButtonProfileDefinition:
    if not isinstance(value, dict) or set(value) != {"schema_version", "slots"}:
        raise ValueError("definition has unexpected fields")
    slots = value["slots"]
    if not isinstance(slots, list):
        raise ValueError("slots must be a list")
    return ButtonProfileDefinition(
        value["schema_version"],
        tuple(None if command is None else decode_button_intent(command) for command in slots),
    )


def decode_button_intent(value: object) -> UserButtonIntent:
    """Rebuild one bindable intent from parsed JSON, refusing unknown or extra fields.

    HTTP request bodies are decoded through here as well (after Pydantic has shape-checked
    them), so the tag vocabulary lives in exactly one place.
    """

    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        raise ValueError("command must be a tagged object")
    tag = value["type"]
    fields = set(value)
    if tag == "select_steering_mode" and fields == {"type", "mode"}:
        return SelectSteeringMode(SteeringMode(value["mode"]))
    if tag == "toggle_automatic_assistance" and fields == {"type"}:
        return ToggleAutomaticAssistance()
    if tag == "adjust_manual_assistance" and fields == {"type", "delta"}:
        return AdjustManualAssistance(value["delta"])
    if tag == "set_manual_assistance_level" and fields == {"type", "level"}:
        return SetManualAssistanceLevel(value["level"])
    if tag == "set_maximum_assistance" and fields == {"type", "enabled"}:
        return SetMaximumAssistance(value["enabled"])
    if tag == "toggle_maximum_assistance" and fields == {"type"}:
        return ToggleMaximumAssistance()
    if tag == "start_high_beam_strobe" and fields == {"type"}:
        return StartHighBeamStrobe()
    raise ValueError(f"unsupported or malformed button command: {tag}")


def button_profile_fingerprint(definition: ButtonProfileDefinition) -> str:
    return sha256(canonical_button_profile_bytes(definition)).hexdigest()
