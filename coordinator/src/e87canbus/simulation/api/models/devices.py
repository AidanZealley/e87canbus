from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt

ByteRequest = Annotated[StrictInt, Field(ge=0, le=255)]


class SimulationDeviceProtocolVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    protocol_version: ByteRequest


class SimulationDeviceStatusCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    status_code: ByteRequest
