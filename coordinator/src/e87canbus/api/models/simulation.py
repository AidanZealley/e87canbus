"""Request models for simulation controls."""

from pydantic import BaseModel, ConfigDict, StrictFloat, StrictInt


class StepRequest(BaseModel):
    button_index: int = 0


class SpeedRequest(BaseModel):
    speed_kph: float


class EngineTelemetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EngineRpmRequest(EngineTelemetryRequest):
    rpm: StrictInt


class TemperatureRequest(EngineTelemetryRequest):
    temperature_c: StrictFloat
