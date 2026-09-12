from typing import Literal

from pydantic import BaseModel, ConfigDict

from e87canbus.panel import CoordinatorStatus


class SimulationCoordinatorPanelState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    coordinator_status: CoordinatorStatus
    coordinator_status_preview: CoordinatorStatus | None


class SimulationCoordinatorStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    status: Literal["starting", "ready", "fault", "off"] | None
