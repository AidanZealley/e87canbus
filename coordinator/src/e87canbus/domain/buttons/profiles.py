"""Button-pad profiles: the durable value, its storage codec, and the running pad.

A profile is one shape everywhere — sixteen slots, each holding what a button does and
what it looks like, or ``None``. The stored row, the JSON on disk, the HTTP body and the
profile the kernel routes presses through all use that same dense tuple, so nothing has
to be converted between representations and no index can mean different things in
different layers.

Which commands may occupy a slot is listed once in :mod:`e87canbus.domain.buttons.catalogue`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, assert_never
from uuid import UUID

from e87canbus.config import (
    BUILT_IN_RESERVED_BUTTON_INDEXES,
    HighBeamStrobeConfig,
    SteeringConfig,
)
from e87canbus.domain.buttons.catalogue import ButtonCommand
from e87canbus.domain.buttons.commands import (
    button_command_configuration_error,
    button_command_has_active_state,
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
from e87canbus.domain.state import RGB_BLUE, RGB_WHITE, Rgb
from e87canbus.domain.timestamps import validate_canonical_utc_timestamp

BUTTON_PROFILE_SCHEMA_VERSION = 2
BUTTON_PROFILE_NAME_MAX_LENGTH = 100
BUILT_IN_PROFILE_ID = "built-in"

# The bounds ``ButtonPadTrackPayload`` enforces when an animation is finally rendered
# into a track. They are restated here, rather than imported from the wire codec the
# domain must not depend on, so an unrunnable animation is rejected where it is
# authored instead of where it is transmitted.
BREATHE_PERIOD_MIN_MS = 250
BREATHE_PERIOD_MAX_MS = 10_000
BLINK_DURATION_MIN_MS = 1
BLINK_DURATION_MAX_MS = 10_000
RGB_CHANNEL_MAX = 255


def _validate_rgb(value: object, label: str) -> None:
    if (
        not isinstance(value, tuple)
        or len(value) != 3
        or any(type(channel) is not int or not 0 <= channel <= RGB_CHANNEL_MAX for channel in value)
    ):
        raise ValueError(f"{label} must be a tuple of three RGB bytes")


@dataclass(frozen=True)
class BreatheAnimation:
    """A continuous fade between two brightnesses for as long as the button is active."""

    period_ms: int
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        if (
            type(self.period_ms) is not int
            or not BREATHE_PERIOD_MIN_MS <= self.period_ms <= BREATHE_PERIOD_MAX_MS
        ):
            raise ValueError(
                f"breathe period must be between {BREATHE_PERIOD_MIN_MS} and "
                f"{BREATHE_PERIOD_MAX_MS} ms"
            )
        for name, brightness in (("minimum", self.minimum), ("maximum", self.maximum)):
            if type(brightness) is not int or not 0 <= brightness <= RGB_CHANNEL_MAX:
                raise ValueError(f"breathe {name} brightness must be between 0 and 255")
        if self.minimum > self.maximum:
            raise ValueError("breathe minimum brightness must not exceed its maximum")


@dataclass(frozen=True)
class BlinkAnimation:
    """A repeating on/off cycle for as long as the button is active."""

    on_ms: int
    off_ms: int

    def __post_init__(self) -> None:
        for name, duration in (("on", self.on_ms), ("off", self.off_ms)):
            if (
                type(duration) is not int
                or not BLINK_DURATION_MIN_MS <= duration <= BLINK_DURATION_MAX_MS
            ):
                raise ValueError(
                    f"blink {name} duration must be between {BLINK_DURATION_MIN_MS} and "
                    f"{BLINK_DURATION_MAX_MS} ms"
                )


SlotAnimation = BreatheAnimation | BlinkAnimation


@dataclass(frozen=True)
class ButtonSlot:
    """One occupied button: what it does, and what it looks like doing it.

    ``active_colour`` is reserved for per-state authoring and must be ``None``, which
    means "``colour`` at full brightness". Storing the field now means a second colour
    later is an editor change and a default rather than a schema migration.

    ``animation`` renders the active state alone - the inactive state is always static
    and faint - so a command with no observable condition has nothing to animate and is
    rejected here rather than at the boundary that happens to be storing it.
    """

    command: ButtonCommand
    colour: Rgb
    active_colour: None = None
    animation: SlotAnimation | None = None

    def __post_init__(self) -> None:
        if not is_button_command(self.command):
            raise ValueError("slots contain an intent that is not user-bindable")
        _validate_rgb(self.colour, "slot colour")
        if self.active_colour is not None:
            raise ValueError("active_colour is reserved and must be null")
        if self.animation is None:
            return
        if not isinstance(self.animation, BreatheAnimation | BlinkAnimation):
            raise TypeError("slot animation must be a breathe or blink animation")
        if not button_command_has_active_state(self.command):
            raise ValueError(
                f"{type(self.command).__name__} has no active state, so it cannot be animated"
            )


@dataclass(frozen=True)
class ButtonProfileDefinition:
    """What every pad button does and looks like, by position; ``None`` is unassigned."""

    schema_version: int
    slots: tuple[ButtonSlot | None, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int:
            raise ValueError("schema_version must be an integer")
        if self.schema_version != BUTTON_PROFILE_SCHEMA_VERSION:
            raise ValueError(f"unsupported button profile schema_version: {self.schema_version}")
        if not isinstance(self.slots, tuple) or len(self.slots) != BUTTON_LED_COUNT:
            raise ValueError(f"slots must be an immutable {BUTTON_LED_COUNT}-entry tuple")
        if any(value is not None and not isinstance(value, ButtonSlot) for value in self.slots):
            raise ValueError("slots must hold a ButtonSlot or nothing")


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
    def slots(self) -> tuple[ButtonSlot | None, ...]:
        return self.definition.slots

    def intent_for_press(self, button_index: int) -> ButtonCommand | None:
        if type(button_index) is not int or not 0 <= button_index < BUTTON_LED_COUNT:
            raise ValueError(f"button_index must be between 0 and {BUTTON_LED_COUNT - 1}")
        slot = self.slots[button_index]
        return None if slot is None else slot.command

    def assigned(self) -> tuple[tuple[int, ButtonSlot], ...]:
        """Every occupied slot as ``(button_index, slot)``, in button order."""

        return tuple((index, slot) for index, slot in enumerate(self.slots) if slot is not None)


def empty_button_profile_definition() -> ButtonProfileDefinition:
    return ButtonProfileDefinition(BUTTON_PROFILE_SCHEMA_VERSION, (None,) * BUTTON_LED_COUNT)


def button_profile_definition_with(
    assignments: Mapping[int, ButtonSlot],
) -> ButtonProfileDefinition:
    """Build a definition from the assigned buttons alone, leaving the rest unassigned.

    A mapping cannot name the same button twice, so "one command per button" holds by
    construction rather than by validation.
    """

    slots: list[ButtonSlot | None] = [None] * BUTTON_LED_COUNT
    for index, slot in assignments.items():
        if type(index) is not int or not 0 <= index < BUTTON_LED_COUNT:
            raise ValueError(f"button_index must be between 0 and {BUTTON_LED_COUNT - 1}")
        slots[index] = slot
    return ButtonProfileDefinition(BUTTON_PROFILE_SCHEMA_VERSION, tuple(slots))


# The compiled-in pad is written in the current shape rather than migrated: it is not a
# stored row. Its colours are what the v1 derivation showed for these commands, so an
# out-of-the-box pad looks the same as it did before colours were authorable.
_BUILT_IN_FIXED_SLOTS: Mapping[int, ButtonSlot] = {
    0: ButtonSlot(ToggleAutomaticAssistance(), RGB_BLUE),
    1: ButtonSlot(AdjustManualAssistance(-1), RGB_WHITE),
    2: ButtonSlot(AdjustManualAssistance(1), RGB_WHITE),
    3: ButtonSlot(ToggleMaximumAssistance(), RGB_WHITE),
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
        {**_BUILT_IN_FIXED_SLOTS, strobe_index: ButtonSlot(StartHighBeamStrobe(), RGB_WHITE)}
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


def encode_button_slot(slot: ButtonSlot) -> dict[str, Any]:
    """Encode one slot for both durable storage and the HTTP boundary."""

    return {
        "command": encode_button_command(slot.command),
        "colour": list(slot.colour),
        "active_colour": slot.active_colour,
        "animation": _encode_animation(slot.animation),
    }


def decode_button_slot(value: object) -> ButtonSlot:
    """Decode one strict slot object; every field is present, including the null ones."""

    if not isinstance(value, dict) or set(value) != {
        "command",
        "colour",
        "active_colour",
        "animation",
    }:
        raise ValueError("button slot has unexpected fields")
    colour = value["colour"]
    if not isinstance(colour, list) or len(colour) != 3:
        raise ValueError("slot colour must be a tuple of three RGB bytes")
    red, green, blue = colour
    return ButtonSlot(
        decode_button_command(value["command"]),
        (red, green, blue),
        value["active_colour"],
        _decode_animation(value["animation"]),
    )


def _encode_animation(animation: SlotAnimation | None) -> dict[str, Any] | None:
    match animation:
        case None:
            return None
        case BreatheAnimation(period_ms=period_ms, minimum=minimum, maximum=maximum):
            return {
                "kind": "breathe",
                "period_ms": period_ms,
                "minimum": minimum,
                "maximum": maximum,
            }
        case BlinkAnimation(on_ms=on_ms, off_ms=off_ms):
            return {"kind": "blink", "on_ms": on_ms, "off_ms": off_ms}
        case _:
            assert_never(animation)


def _decode_animation(value: object) -> SlotAnimation | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
        raise ValueError("slot animation must be a tagged object")
    kind = value["kind"]
    if kind == "breathe" and set(value) == {"kind", "period_ms", "minimum", "maximum"}:
        return BreatheAnimation(value["period_ms"], value["minimum"], value["maximum"])
    if kind == "blink" and set(value) == {"kind", "on_ms", "off_ms"}:
        return BlinkAnimation(value["on_ms"], value["off_ms"])
    raise ValueError(f"unsupported or malformed slot animation: {kind}")


def canonical_button_profile_bytes(definition: ButtonProfileDefinition) -> bytes:
    value = {
        "schema_version": definition.schema_version,
        "slots": [None if slot is None else encode_button_slot(slot) for slot in definition.slots],
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
        tuple(None if slot is None else decode_button_slot(slot) for slot in slots),
    )


def button_profile_fingerprint(definition: ButtonProfileDefinition) -> str:
    return sha256(canonical_button_profile_bytes(definition)).hexdigest()


def validate_button_profile_for(
    definition: ButtonProfileDefinition,
    steering_config: SteeringConfig,
) -> None:
    """Reject a well-formed profile that this vehicle's configuration cannot run."""

    for index, slot in enumerate(definition.slots):
        if slot is None:
            continue
        reason = button_command_configuration_error(slot.command, steering_config)
        if reason is not None:
            raise ValueError(f"button {index}: {reason}")
