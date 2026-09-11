"""Non-secret first-boot provisioning status exposed to operators."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class ProvisioningStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    format_version: Literal[1]
    role: Literal["coordinator", "console"]
    installation_id: Annotated[str, StringConstraints(pattern=r"^[a-z2-7]{52}$")]
    device_id: Annotated[
        str,
        StringConstraints(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"),
    ]
    hostname: Annotated[
        str,
        StringConstraints(
            min_length=1,
            max_length=63,
            pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
        ),
    ]
    completed_phase: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    artifact_digests: dict[
        Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,31}$")],
        Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")],
    ] = Field(max_length=8)
    result: Literal["pending", "succeeded", "failed"]
    error_code: Annotated[str, StringConstraints(min_length=1, max_length=64)] | None
