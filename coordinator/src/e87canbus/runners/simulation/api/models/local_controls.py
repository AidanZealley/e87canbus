from pydantic import BaseModel, ConfigDict


class SimulatedConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    connected: bool


class SimulatedFailureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    enabled: bool
