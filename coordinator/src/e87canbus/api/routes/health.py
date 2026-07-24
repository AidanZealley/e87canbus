"""Kubernetes-style process liveness and controller readiness routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from e87canbus.api.models.health import (
    LivenessResponse,
    ReadinessResponse,
    RuntimeCapabilities,
    RuntimeConfigurationResponse,
)
from e87canbus.deployment import SimulationApiScope

router = APIRouter(tags=["health"])


@router.get(
    "/health/live",
    operation_id="checkLiveness",
    response_model=LivenessResponse,
)
async def live() -> LivenessResponse:
    return LivenessResponse()


@router.get(
    "/health/ready",
    operation_id="checkReadiness",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
async def ready(request: Request) -> JSONResponse:
    service = request.app.state.controller_service
    payload = ReadinessResponse(
        status="ready" if service.ready else "not_ready",
        boot_id=service.boot_id,
    )
    return JSONResponse(
        status_code=200 if service.ready else 503,
        content=payload.model_dump(mode="json"),
    )


@router.get(
    "/api/runtime",
    operation_id="getRuntimeConfiguration",
    response_model=RuntimeConfigurationResponse,
)
async def runtime_configuration(request: Request) -> RuntimeConfigurationResponse:
    deployment = request.app.state.deployment
    return RuntimeConfigurationResponse(
        profile=deployment.profile,
        capabilities=RuntimeCapabilities(
            simulated_vehicle=deployment.simulation_api
            in {SimulationApiScope.VEHICLE, SimulationApiScope.FULL},
            simulation_workbench=deployment.simulation_api is SimulationApiScope.FULL,
        ),
    )
