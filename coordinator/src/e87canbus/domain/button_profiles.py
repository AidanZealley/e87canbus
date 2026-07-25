"""Button-pad profiles: the durable value, its storage codec, and the running pad.

A profile is one shape everywhere — sixteen slots, each holding an assignable command
or ``None``. The stored row, the JSON on disk, the HTTP body and the profile the kernel
routes presses through all use that same dense tuple, so nothing has to be converted
between representations and no index can mean different things in different layers.

Which commands may occupy a slot is defined once in :mod:`e87canbus.domain.button_commands`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from e87canbus.config import (
    BUILT_IN_RESERVED_BUTTON_INDEXES,
    HighBeamStrobeConfig,
    SteeringConfig,
)
from e87canbus.domain.button_commands import (
    ButtonCommand,
    button_command_configuration_error,
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
BUTTON_PROFILE_KIND = "button profile"
BUILT_IN_PROFILE_ID = "built-in"


@dataclass(frozen=True)
class ButtonProfileDefinition:
    """What every pad button does, by position; ``None`` leaves a button unassigned."""

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

    def as_active(self) -> ActiveButtonProfile:
        return ActiveButtonProfile(self.profile_id, self.definition)


@dataclass(frozen=True)
class ActiveButtonProfile:
    """The profile the pad is running: a stored profile's identity and its slots.

    ``profile_id`` is the stored UUID once a saved profile has been activated, and
    ``BUILT_IN_PROFILE_ID`` while the compiled-in default is in force; live state
    reports it so a client can tell which saved revision the pad is obeying.
    """

    profile_id: str
    definition: ButtonProfileDefinition

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str):
            raise TypeError("profile_id must be a string")
        if not self.profile_id or self.profile_id.strip() != self.profile_id:
            raise ValueError("profile_id must be a non-empty trimmed string")
        if not isinstance(self.definition, ButtonProfileDefinition):
            raise TypeError("definition must be a ButtonProfileDefinition")

    @property
    def slots(self) -> tuple[ButtonCommand | None, ...]:
        return self.definition.slots

    def intent_for_press(self, button_index: int) -> ButtonCommand | None:
        if type(button_index) is not int or not 0 <= button_index < BUTTON_LED_COUNT:
            raise ValueError(f"button_index must be between 0 and {BUTTON_LED_COUNT - 1}")
        return self.slots[button_index]

    def assigned(self) -> tuple[tuple[int, ButtonCommand], ...]:
        """Every occupied slot as ``(button_index, command)``, in button order."""

        return tuple(
            (index, command) for index, command in enumerate(self.slots) if command is not None
        )


def empty_button_profile_definition() -> ButtonProfileDefinition:
    return ButtonProfileDefinition(BUTTON_PROFILE_SCHEMA_VERSION, (None,) * BUTTON_LED_COUNT)


def button_profile_definition_with(
    assignments: Mapping[int, ButtonCommand],
) -> ButtonProfileDefinition:
    """Build a definition from the assigned buttons alone, leaving the rest unassigned.

    A mapping cannot name the same button twice, so "one command per button" holds by
    construction rather than by validation.
    """

    slots: list[ButtonCommand | None] = [None] * BUTTON_LED_COUNT
    for index, command in assignments.items():
        if type(index) is not int or not 0 <= index < BUTTON_LED_COUNT:
            raise ValueError(f"button_index must be between 0 and {BUTTON_LED_COUNT - 1}")
        slots[index] = command
    return ButtonProfileDefinition(BUTTON_PROFILE_SCHEMA_VERSION, tuple(slots))


_BUILT_IN_FIXED_SLOTS: Mapping[int, ButtonCommand] = {
    0: ToggleAutomaticAssistance(),
    1: AdjustManualAssistance(-1),
    2: AdjustManualAssistance(1),
    3: ToggleMaximumAssistance(),
}

if set(_BUILT_IN_FIXED_SLOTS) != BUILT_IN_RESERVED_BUTTON_INDEXES:
    raise RuntimeError(
        "built-in fixed button slots must match config.BUILT_IN_RESERVED_BUTTON_INDEXES"
    )


def built_in_button_profile_definition(
    high_beam_strobe_config: HighBeamStrobeConfig | None = None,
) -> ButtonProfileDefinition:
    """The default pad, with the strobe wherever its configuration puts it.

    This is the only description of the default pad: it is what a fresh database is
    seeded with and what the runtime falls back to before a saved profile is loaded,
    so the two can never disagree about what an out-of-the-box button does. The strobe
    index is validated by ``HighBeamStrobeConfig`` to fall outside the reserved slots.
    """

    strobe_index = (high_beam_strobe_config or HighBeamStrobeConfig()).button_index
    return button_profile_definition_with(
        {**_BUILT_IN_FIXED_SLOTS, strobe_index: StartHighBeamStrobe()}
    )


def built_in_active_button_profile(
    high_beam_strobe_config: HighBeamStrobeConfig | None = None,
) -> ActiveButtonProfile:
    """The compiled-in pad the kernel runs until a saved profile is activated."""

    return ActiveButtonProfile(
        BUILT_IN_PROFILE_ID, built_in_button_profile_definition(high_beam_strobe_config)
    )


BUILT_IN_BUTTON_PROFILE = built_in_button_profile_definition()


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


def validate_button_profile_for(
    definition: ButtonProfileDefinition,
    steering_config: SteeringConfig,
) -> None:
    """Reject a well-formed profile that this vehicle's configuration cannot run."""

    for index, command in enumerate(definition.slots):
        if command is None:
            continue
        reason = button_command_configuration_error(command, steering_config)
        if reason is not None:
            raise ValueError(f"button {index}: {reason}")


class ButtonProfileRepository(Protocol):
    """Durable button-profile storage, including which profile is selected."""

    def list_profiles(self) -> tuple[StoredButtonProfile, ...]: ...
    def get_profile(self, profile_id: str) -> StoredButtonProfile | None: ...
    def get_selected_profile(self) -> StoredButtonProfile: ...
    def select_profile(self, profile_id: str, expected_revision: int) -> StoredButtonProfile: ...
    def create_profile(
        self, name: str, definition: ButtonProfileDefinition | None = None
    ) -> StoredButtonProfile: ...
    def update_profile(
        self,
        profile_id: str,
        expected_revision: int,
        name: str,
        definition: ButtonProfileDefinition,
    ) -> StoredButtonProfile: ...
    def delete_profile(self, profile_id: str, expected_revision: int) -> None: ...
