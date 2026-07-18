"""Steering curve and stored-profile routes."""

from fastapi import APIRouter, Path, Query, Request

from e87canbus.api.errors import api_problem_responses
from e87canbus.api.internal import steering
from e87canbus.api.models.steering import (
    CANONICAL_UUID_PATTERN,
    CreateProfileRequest,
    SteeringProfileResponse,
    UpdateProfileRequest,
)
from e87canbus.features.steering import StoredSteeringProfile

router = APIRouter(prefix="/api/steering", tags=["steering"])


@router.get(
    "/profiles",
    operation_id="listSteeringProfiles",
    response_model=list[SteeringProfileResponse],
    responses=api_problem_responses(422, 503),
)
async def list_steering_profiles(
    request: Request,
) -> tuple[StoredSteeringProfile, ...]:
    return await steering.list_profiles(request.app.state.profile_repository)


@router.get(
    "/profile",
    operation_id="getSavedSteeringProfile",
    response_model=SteeringProfileResponse,
    responses=api_problem_responses(404, 503),
)
async def get_saved_steering_profile(
    request: Request,
) -> StoredSteeringProfile:
    return await steering.get_saved_profile(request.app.state.profile_repository)


@router.post(
    "/profiles",
    status_code=201,
    operation_id="createSteeringProfile",
    response_model=SteeringProfileResponse,
    responses=api_problem_responses(409, 422, 503),
)
async def create_steering_profile(
    request: Request,
    body: CreateProfileRequest,
) -> StoredSteeringProfile:
    return await steering.create_profile(
        request.app,
        request.app.state.profile_repository,
        body,
    )


@router.get(
    "/profiles/{profile_id}",
    operation_id="getSteeringProfile",
    response_model=SteeringProfileResponse,
    responses=api_problem_responses(404, 422, 503),
)
async def get_steering_profile(
    request: Request,
    profile_id: str = Path(pattern=CANONICAL_UUID_PATTERN),
) -> StoredSteeringProfile:
    return await steering.get_profile(request.app.state.profile_repository, profile_id)


@router.put(
    "/profiles/{profile_id}",
    operation_id="updateSteeringProfile",
    response_model=SteeringProfileResponse,
    responses=api_problem_responses(404, 409, 422, 503),
)
async def update_steering_profile(
    request: Request,
    body: UpdateProfileRequest,
    profile_id: str = Path(pattern=CANONICAL_UUID_PATTERN),
) -> StoredSteeringProfile:
    return await steering.update_profile(
        request.app,
        request.app.state.profile_repository,
        profile_id,
        body,
    )


@router.delete(
    "/profiles/{profile_id}",
    status_code=204,
    operation_id="deleteSteeringProfile",
    responses=api_problem_responses(404, 409, 422, 503),
)
async def delete_steering_profile(
    request: Request,
    expected_revision: int = Query(ge=1),
    profile_id: str = Path(pattern=CANONICAL_UUID_PATTERN),
) -> None:
    await steering.delete_profile(
        request.app,
        request.app.state.profile_repository,
        profile_id,
        expected_revision,
    )
