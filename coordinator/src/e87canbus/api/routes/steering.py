"""Steering routes: live assistance controls and stored-profile CRUD.

Everything a consumer does with steering lives under ``/api/steering``. The two
kinds of endpoint are kept in separate sections: imperative controls that act on
the live controller now, and CRUD on durable saved profiles. Their use cases live
in the ``operational_commands`` and ``steering`` internal modules respectively.
"""

from fastapi import APIRouter, Path, Query, Request

from e87canbus.api.errors import api_problem_responses
from e87canbus.api.internal import operational_commands, steering
from e87canbus.api.models.commands import (
    ActivateSteeringCurveRequest,
    ActivateSteeringProfileRequest,
    AdjustManualAssistanceRequest,
    CommandAcknowledgement,
    SetManualAssistanceLevelRequest,
    SetMaximumAssistanceRequest,
    SetSteeringModeRequest,
)
from e87canbus.api.models.steering import (
    CANONICAL_UUID_PATTERN,
    CreateProfileRequest,
    SteeringProfileResponse,
    UpdateProfileRequest,
)
from e87canbus.domain.steering import StoredSteeringProfile

router = APIRouter(prefix="/api/steering", tags=["steering"])


# --- Live assistance controls (act on the running controller) ---------------


@router.put(
    "/maximum-assistance",
    operation_id="setMaximumAssistance",
    responses=api_problem_responses(409, 422, 503),
)
async def set_maximum_assistance(
    request: Request,
    body: SetMaximumAssistanceRequest,
) -> CommandAcknowledgement:
    return await operational_commands.set_maximum_assistance(request.app, body)


@router.put(
    "/mode",
    operation_id="setSteeringMode",
    responses=api_problem_responses(409, 422, 503),
)
async def set_steering_mode(
    request: Request,
    body: SetSteeringModeRequest,
) -> CommandAcknowledgement:
    return await operational_commands.set_steering_mode(request.app, body)


@router.post(
    "/manual-assistance-adjustment",
    operation_id="adjustManualAssistance",
    responses=api_problem_responses(409, 422, 503),
)
async def adjust_manual_assistance(
    request: Request,
    body: AdjustManualAssistanceRequest,
) -> CommandAcknowledgement:
    return await operational_commands.adjust_manual_assistance(request.app, body)


@router.put(
    "/manual-assistance-level",
    operation_id="setManualAssistanceLevel",
    responses=api_problem_responses(409, 422, 503),
)
async def set_manual_assistance_level(
    request: Request,
    body: SetManualAssistanceLevelRequest,
) -> CommandAcknowledgement:
    return await operational_commands.set_manual_assistance_level(request.app, body)


@router.post(
    "/activate-profile",
    operation_id="activateSteeringProfile",
    responses=api_problem_responses(404, 409, 422, 503),
)
async def activate_steering_profile(
    request: Request,
    body: ActivateSteeringProfileRequest,
) -> CommandAcknowledgement:
    return await operational_commands.activate_steering_profile(
        request.app,
        request.app.state.profile_repository,
        body,
    )


@router.put(
    "/curve",
    operation_id="activateSteeringCurve",
    responses=api_problem_responses(409, 422, 503),
)
async def activate_steering_curve(
    request: Request,
    body: ActivateSteeringCurveRequest,
) -> CommandAcknowledgement:
    return await operational_commands.activate_steering_curve(request.app, body)


# --- Stored steering-profile CRUD (durable resources) -----------------------


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
