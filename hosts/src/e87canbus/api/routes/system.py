"""Operator-only host system routes."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from e87canbus.api.models.provisioning import ProvisioningStatusResponse

PROVISIONING_STATUS_PATH = Path("/var/lib/e87canbus-provisioning/status.json")
MAX_PROVISIONING_STATUS_BYTES = 32 * 1024

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get(
    "/provisioning",
    operation_id="getProvisioningStatus",
    response_model=ProvisioningStatusResponse,
    responses={503: {"description": "Provisioning status unavailable"}},
)
async def provisioning_status(request: Request) -> ProvisioningStatusResponse:
    try:
        path: Path = request.app.state.provisioning_status_path
        with path.open("rb") as status_file:
            contents = status_file.read(MAX_PROVISIONING_STATUS_BYTES + 1)
        if len(contents) > MAX_PROVISIONING_STATUS_BYTES:
            raise ValueError
        return ProvisioningStatusResponse.model_validate_json(contents, strict=True)
    except (OSError, ValueError, ValidationError):
        raise HTTPException(status_code=503, detail="provisioning status unavailable") from None
