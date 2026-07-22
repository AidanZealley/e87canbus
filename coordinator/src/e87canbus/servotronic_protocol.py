"""Fixed v1 Servotronic RAM-curve protocol carried over the bench ISO-TP link."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from enum import IntEnum

from e87canbus.features.steering import STEERING_CURVE_SCHEMA_VERSION, SteeringCurveDefinition

PROTOCOL_VERSION = 1
INTERPOLATION_MONOTONE_CUBIC_V1 = 1
SET_CURVE_OPCODE = 1
STATUS_OPCODE = 2
SET_CONTROL_OPCODE = 3
SET_CURVE_LENGTH = 44
STATUS_LENGTH = 19


class CurveResult(IntEnum):
    ACCEPTED = 0
    BAD_LENGTH = 1
    UNSUPPORTED = 2
    BAD_GRID = 3
    BAD_VALUES = 4
    BAD_CRC = 5


class CurveSource(IntEnum):
    BUILTIN_FALLBACK = 0
    COORDINATOR_RAM = 1


class ControlMode(IntEnum):
    AUTO = 0
    MANUAL = 1
    MAXIMUM = 2


# Canonical wire spellings shared with firmware and the frontend contract.  Keep these
# strings identical to the device/UI vocabulary; they are the single source for the live
# ``ObservedServotronicSnapshot`` string fields.
CONTROL_MODE_WIRE: dict[ControlMode, str] = {
    ControlMode.AUTO: "auto",
    ControlMode.MANUAL: "manual",
    ControlMode.MAXIMUM: "maximum",
}

CURVE_SOURCE_WIRE: dict[CurveSource, str] = {
    CurveSource.BUILTIN_FALLBACK: "builtin_fallback",
    CurveSource.COORDINATOR_RAM: "coordinator_ram",
}

# ``ServotronicStatus.inhibit_reason`` is a raw controller code; values beyond the known
# range clamp to the last (``can_fault``) label, matching the firmware reporting.
INHIBIT_REASON_WIRE: tuple[str, ...] = (
    "none",
    "no_speed",
    "stale_speed",
    "invalid_speed",
    "can_fault",
)


def inhibit_reason_wire(inhibit_reason: int) -> str:
    """Map a raw controller inhibit code to its canonical wire spelling."""

    return INHIBIT_REASON_WIRE[min(inhibit_reason, len(INHIBIT_REASON_WIRE) - 1)]


@dataclass(frozen=True)
class ServotronicStatus:
    result: CurveResult
    source: CurveSource
    activation_revision: int
    curve_crc32: int
    speed_deci_kph: int
    assistance_per_mille: int
    pwm_duty: int
    speed_fresh: bool
    inhibit_reason: int
    control_mode: ControlMode = ControlMode.AUTO


def pack_curve(definition: SteeringCurveDefinition, activation_revision: int) -> bytes:
    if not 0 <= activation_revision <= 0xFFFFFFFF:
        raise ValueError("activation revision must fit uint32")
    header = struct.pack(
        "<BBBBI8H8H",
        PROTOCOL_VERSION,
        SET_CURVE_OPCODE,
        STEERING_CURVE_SCHEMA_VERSION,
        INTERPOLATION_MONOTONE_CUBIC_V1,
        activation_revision,
        *(point.speed_deci_kph for point in definition.points),
        *(point.assistance_per_mille for point in definition.points),
    )
    return header + struct.pack("<I", zlib.crc32(header))


def pack_control(assistance: float, mode: ControlMode) -> bytes:
    if not 0.0 <= assistance <= 1.0:
        raise ValueError("assistance must be between zero and one")
    return struct.pack(
        "<BBHB",
        PROTOCOL_VERSION,
        SET_CONTROL_OPCODE,
        round(assistance * 1000),
        mode,
    )


def unpack_status(payload: bytes) -> ServotronicStatus:
    if len(payload) != STATUS_LENGTH:
        raise ValueError("invalid Servotronic status payload length")
    version, opcode, result, source, revision, crc, speed, assistance, duty, flags, inhibit = (
        struct.unpack("<BBBBIIHHBBB", payload)
    )
    if version != PROTOCOL_VERSION or opcode != STATUS_OPCODE:
        raise ValueError("unsupported Servotronic status protocol")
    return ServotronicStatus(
        CurveResult(result), CurveSource(source), revision, crc, speed, assistance, duty,
        bool(flags & 1), inhibit, ControlMode((flags >> 1) & 0x03),
    )
