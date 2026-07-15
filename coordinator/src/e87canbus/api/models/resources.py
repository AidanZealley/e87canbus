"""Precise durable-resource invalidation payloads."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResourceChangedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    type: Literal["resources.changed"] = "resources.changed"
    resource: Literal["settings", "steering_profile"]
    id: str | None
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_identity(self) -> "ResourceChangedEvent":
        if self.resource == "settings" and self.id is not None:
            raise ValueError("settings resource changes must not carry an id")
        if self.resource == "steering_profile" and self.id is None:
            raise ValueError("steering profile resource changes require an id")
        return self
