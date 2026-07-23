from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt

from e87canbus.runners.simulation.protocol import (
    MAX_SIMULATED_ENGINE_RPM,
    MAX_SIMULATED_SPEED_KPH,
    MAX_SIMULATED_TEMPERATURE_C,
    MIN_SIMULATED_TEMPERATURE_C,
)


class SpeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    speed_kph: float = Field(ge=0, le=MAX_SIMULATED_SPEED_KPH)


class EngineTelemetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EngineRpmRequest(EngineTelemetryRequest):
    rpm: Annotated[StrictInt, Field(ge=0, le=MAX_SIMULATED_ENGINE_RPM)]


class TemperatureRequest(EngineTelemetryRequest):
    temperature_c: Annotated[
        StrictFloat,
        Field(ge=MIN_SIMULATED_TEMPERATURE_C, le=MAX_SIMULATED_TEMPERATURE_C),
    ]
