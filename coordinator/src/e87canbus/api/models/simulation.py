"""Request models for simulation controls."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictFloat, StrictInt


class StepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    button_index: int = 0


class SpeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    speed_kph: float


class EngineTelemetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EngineRpmRequest(EngineTelemetryRequest):
    rpm: StrictInt


class TemperatureRequest(EngineTelemetryRequest):
    temperature_c: StrictFloat


class DeviceStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["online", "degraded", "offline"]
