"""Durable, user-authored button-pad profile values and their storage codec."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from e87canbus.domain.button_commands import (
    ButtonCommand,
    decode_button_command,
    encode_button_command,
    is_button_command,
)
from e87canbus.domain.events import BUTTON_LED_COUNT
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    StartHighBeamStrobe,
    ToggleAutomaticAssistance,
    ToggleMaximumAssistance,
)
from e87canbus.domain.revisioned_profiles import (
    validate_saved_profile_revision as validate_saved_profile_revision,
)
from e87canbus.domain.timestamps import validate_canonical_utc_timestamp

BUTTON_PROFILE_SCHEMA_VERSION = 1
BUTTON_PROFILE_NAME_MAX_LENGTH = 100


@dataclass(frozen=True)
class ButtonProfileDefinition:
    schema_version: int
    slots: tuple[ButtonCommand | None, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int:
            raise ValueError("schema_version must be an integer")
        if self.schema_version != BUTTON_PROFILE_SCHEMA_VERSION:
            raise ValueError(f"unsupported button profile schema_version: {self.schema_version}")
        if not isinstance(self.slots, tuple) or len(self.slots) != BUTTON_LED_COUNT:
            raise ValueError(f"slots must be an immutable {BUTTON_LED_COUNT}-entry tuple")
        if any(value is not None and not is_button_command(value) for value in self.slots):
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


def canonical_button_profile_bytes(definition: ButtonProfileDefinition) -> bytes:
    value = {
        "schema_version": definition.schema_version,
        "slots": [
            None if command is None else encode_button_command(command)
            for command in definition.slots
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
        tuple(None if command is None else decode_button_command(command) for command in slots),
    )


def button_profile_fingerprint(definition: ButtonProfileDefinition) -> str:
    return sha256(canonical_button_profile_bytes(definition)).hexdigest()
