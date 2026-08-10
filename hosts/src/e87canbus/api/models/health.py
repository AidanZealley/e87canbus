"""Health endpoint response models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from e87canbus.deployment import DeploymentProfile


class LivenessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["live"] = "live"


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ready", "not_ready"]
    boot_id: str = Field(min_length=1)


class RuntimeCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    simulated_vehicle: bool
    simulation_workbench: bool


class RuntimeConfigurationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: DeploymentProfile
    capabilities: RuntimeCapabilities
