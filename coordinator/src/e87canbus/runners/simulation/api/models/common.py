from typing import Literal

from pydantic import BaseModel, ConfigDict


class SimulationCommandAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    accepted: Literal[True] = True
    boot_id: str
