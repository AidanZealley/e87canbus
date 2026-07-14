"""Request models for simulation controls."""

from pydantic import BaseModel


class StepRequest(BaseModel):
    button_index: int = 0


class SpeedRequest(BaseModel):
    speed_kph: float
