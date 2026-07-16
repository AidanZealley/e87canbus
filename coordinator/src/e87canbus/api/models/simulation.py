"""Request models for simulation controls."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt


class SimulationCommandAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    accepted: Literal[True] = True
    boot_id: str


class SpeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    speed_kph: float


class EngineTelemetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EngineRpmRequest(EngineTelemetryRequest):
    rpm: StrictInt


class TemperatureRequest(EngineTelemetryRequest):
    temperature_c: StrictFloat


ByteRequest = Annotated[StrictInt, Field(ge=0, le=255)]


class SimulationDeviceProtocolVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    protocol_version: ByteRequest


class SimulationDeviceStatusCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    status_code: ByteRequest
