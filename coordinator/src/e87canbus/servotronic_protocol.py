"""Fixed v1 Servotronic RAM-curve protocol carried over the bench ISO-TP link."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from enum import IntEnum

from e87canbus.features.steering import (
    STEERING_CURVE_SCHEMA_VERSION,
    STEERING_CURVE_V1_SPEEDS_DECI_KPH,
    SteeringCurveDefinition,
    SteeringCurvePoint,
)

PROTOCOL_VERSION = 1
INTERPOLATION_MONOTONE_CUBIC_V1 = 1
SET_CURVE_OPCODE = 1
STATUS_OPCODE = 2
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


def unpack_curve(payload: bytes) -> tuple[SteeringCurveDefinition, int, int]:
    if len(payload) != SET_CURVE_LENGTH:
        raise ValueError("invalid Servotronic curve payload length")
    if zlib.crc32(payload[:-4]) != struct.unpack_from("<I", payload, 40)[0]:
        raise ValueError("invalid Servotronic curve CRC")
    version, opcode, schema, interpolation, revision, *values = struct.unpack(
        "<BBBBI8H8HI", payload
    )
    if (version, opcode, schema, interpolation) != (
        PROTOCOL_VERSION,
        SET_CURVE_OPCODE,
        STEERING_CURVE_SCHEMA_VERSION,
        INTERPOLATION_MONOTONE_CUBIC_V1,
    ):
        raise ValueError("unsupported Servotronic curve protocol")
    speeds, assistance = values[:8], values[8:16]
    definition = SteeringCurveDefinition(
        schema,
        tuple(
            SteeringCurvePoint(speed, value)
            for speed, value in zip(speeds, assistance, strict=True)
        ),
    )
    if tuple(speeds) != STEERING_CURVE_V1_SPEEDS_DECI_KPH:
        raise ValueError("invalid Servotronic curve speed grid")
    return definition, revision, values[16]


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
        bool(flags & 1), inhibit,
    )


def pack_status(status: ServotronicStatus) -> bytes:
    return struct.pack(
        "<BBBBIIHHBBB",
        PROTOCOL_VERSION,
        STATUS_OPCODE,
        status.result,
        status.source,
        status.activation_revision,
        status.curve_crc32,
        status.speed_deci_kph,
        status.assistance_per_mille,
        status.pwm_duty,
        int(status.speed_fresh),
        status.inhibit_reason,
    )
