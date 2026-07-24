"""Button-pad profile CRUD and live activation routes."""

from fastapi import APIRouter, Path, Query, Request

from e87canbus.api.errors import api_problem_responses
from e87canbus.api.internal import button_profiles
from e87canbus.api.models.button_profiles import (
    ActivateButtonProfileRequest,
    ButtonProfileResponse,
    CreateButtonProfileRequest,
    UpdateButtonProfileRequest,
)
from e87canbus.api.models.commands import CommandAcknowledgement
from e87canbus.api.models.steering import CANONICAL_UUID_PATTERN

router = APIRouter(prefix="/api/button-pad", tags=["button-pad"])


@router.post(
    "/activate-profile",
    operation_id="activateButtonProfile",
    responses=api_problem_responses(404, 409, 422, 503),
)
async def activate_button_profile(
    request: Request, body: ActivateButtonProfileRequest
) -> CommandAcknowledgement:
    return await button_profiles.activate_profile(
        request.app, request.app.state.button_profile_repository, body
    )


@router.get(
    "/profiles",
    operation_id="listButtonProfiles",
    response_model=list[ButtonProfileResponse],
    responses=api_problem_responses(422, 503),
)
async def list_button_profiles(request: Request) -> list[ButtonProfileResponse]:
    return await button_profiles.list_profiles(request.app.state.button_profile_repository)


@router.get(
    "/profile",
    operation_id="getSavedButtonProfile",
    response_model=ButtonProfileResponse,
    responses=api_problem_responses(404, 503),
)
async def get_saved_button_profile(request: Request) -> ButtonProfileResponse:
    return await button_profiles.get_saved_profile(request.app.state.button_profile_repository)


@router.post(
    "/profiles",
    status_code=201,
    operation_id="createButtonProfile",
    response_model=ButtonProfileResponse,
    responses=api_problem_responses(409, 422, 503),
)
async def create_button_profile(
    request: Request, body: CreateButtonProfileRequest
) -> ButtonProfileResponse:
    return await button_profiles.create_profile(
        request.app, request.app.state.button_profile_repository, body
    )


@router.get(
    "/profiles/{profile_id}",
    operation_id="getButtonProfile",
    response_model=ButtonProfileResponse,
    responses=api_problem_responses(404, 422, 503),
)
async def get_button_profile(
    request: Request,
    profile_id: str = Path(pattern=CANONICAL_UUID_PATTERN),
) -> ButtonProfileResponse:
    return await button_profiles.get_profile(
        request.app.state.button_profile_repository, profile_id
    )


@router.put(
    "/profiles/{profile_id}",
    operation_id="updateButtonProfile",
    response_model=ButtonProfileResponse,
    responses=api_problem_responses(404, 409, 422, 503),
)
async def update_button_profile(
    request: Request,
    body: UpdateButtonProfileRequest,
    profile_id: str = Path(pattern=CANONICAL_UUID_PATTERN),
) -> ButtonProfileResponse:
    return await button_profiles.update_profile(
        request.app, request.app.state.button_profile_repository, profile_id, body
    )


@router.delete(
    "/profiles/{profile_id}",
    status_code=204,
    operation_id="deleteButtonProfile",
    responses=api_problem_responses(404, 409, 422, 503),
)
async def delete_button_profile(
    request: Request,
    expected_revision: int = Query(ge=1),
    profile_id: str = Path(pattern=CANONICAL_UUID_PATTERN),
) -> None:
    await button_profiles.delete_profile(
        request.app,
        request.app.state.button_profile_repository,
        profile_id,
        expected_revision,
    )
