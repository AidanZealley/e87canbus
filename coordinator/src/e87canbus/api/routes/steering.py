"""Steering curve and stored-profile routes."""

from fastapi import APIRouter, Query, Request

from e87canbus.api.internal import steering
from e87canbus.api.models.steering import (
    CreateProfileRequest,
    UpdateProfileRequest,
)
from e87canbus.features.steering import StoredSteeringProfile

router = APIRouter(prefix="/api/steering", tags=["steering"])


@router.get("/profiles")
async def list_steering_profiles(
    request: Request,
) -> dict[str, tuple[StoredSteeringProfile, ...]]:
    return await steering.list_profiles(request.app.state.profile_repository)


@router.post("/profiles", status_code=201)
async def create_steering_profile(
    request: Request,
    body: CreateProfileRequest,
) -> StoredSteeringProfile:
    return await steering.create_profile(
        request.app,
        request.app.state.profile_repository,
        body,
    )


@router.get("/profiles/{profile_id}")
async def get_steering_profile(
    request: Request,
    profile_id: str,
) -> StoredSteeringProfile:
    return await steering.get_profile(request.app.state.profile_repository, profile_id)


@router.put("/profiles/{profile_id}")
async def update_steering_profile(
    request: Request,
    profile_id: str,
    body: UpdateProfileRequest,
) -> StoredSteeringProfile:
    return await steering.update_profile(
        request.app,
        request.app.state.profile_repository,
        profile_id,
        body,
    )


@router.delete("/profiles/{profile_id}", status_code=204)
async def delete_steering_profile(
    request: Request,
    profile_id: str,
    expected_revision: int = Query(ge=1),
) -> None:
    await steering.delete_profile(
        request.app,
        request.app.state.profile_repository,
        profile_id,
        expected_revision,
    )
