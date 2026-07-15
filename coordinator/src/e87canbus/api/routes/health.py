"""Kubernetes-style process liveness and controller readiness routes."""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/health/ready")
async def ready(request: Request) -> JSONResponse:
    service = request.app.state.controller_service
    payload: dict[str, Any] = {
        "status": "ready" if service.ready else "not_ready",
        "boot_id": service.boot_id,
    }
    return JSONResponse(status_code=200 if service.ready else 503, content=payload)
