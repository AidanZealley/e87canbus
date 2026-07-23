"""Stable identities for synthetic scalar vehicle signals."""

from enum import StrEnum


class VehicleSignal(StrEnum):
    SPEED = "speed"
    RPM = "rpm"
    OIL_TEMPERATURE = "oil_temperature"
    COOLANT_TEMPERATURE = "coolant_temperature"
