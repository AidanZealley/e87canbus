"""FastAPI lifecycle bridge for the unified controller service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from e87canbus.adapters.sqlite_database import SqliteApplicationDatabase
from e87canbus.adapters.sqlite_profiles import BUILT_IN_PROFILE_ID
from e87canbus.api.internal.live import LiveStatePublisher
from e87canbus.domain.buttons.repository import ButtonProfileRepository
from e87canbus.domain.steering.curves import (
    initial_active_steering_curve,
)
from e87canbus.domain.steering.repository import SteeringProfileRepository
from e87canbus.local_controls.model import CoordinatorCondition, CoordinatorConditionChanged
from e87canbus.local_controls.service import LocalControlsService, LocalControlsServiceError
from e87canbus.service import ControllerLoop


def create_lifespan(
    service: ControllerLoop,
    database: SqliteApplicationDatabase | None,
    profiles: SteeringProfileRepository,
    button_profiles: ButtonProfileRepository,
    publisher: LiveStatePublisher,
    local_controls: LocalControlsService | None = None,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if local_controls is not None:
            await asyncio.to_thread(local_controls.start, publisher.offer_local_controls)
        try:
            await _initialize_controller(
                service,
                database,
                profiles,
                button_profiles,
            )
        except BaseException as exc:
            await _handle_initialization_failure(service, local_controls, exc)
            raise

        try:
            await _start_controller(service, publisher)
        except BaseException:
            await _handle_start_failure(service, publisher, local_controls)
            raise
        try:
            yield
        finally:
            await _shutdown(service, publisher, local_controls)

    return lifespan


async def _initialize_controller(
    service: ControllerLoop,
    database: SqliteApplicationDatabase | None,
    profiles: SteeringProfileRepository,
    button_profiles: ButtonProfileRepository,
) -> None:
    if database is not None:
        await asyncio.to_thread(database.initialize)
    if service.load_persisted_steering_curve:
        stored_profiles = await asyncio.to_thread(profiles.list_profiles)
        if stored_profiles:
            saved = next(
                (
                    profile
                    for profile in stored_profiles
                    if profile.profile_id == BUILT_IN_PROFILE_ID
                ),
                stored_profiles[0],
            )
            service.configure_initial_steering_curve(
                initial_active_steering_curve(
                    saved.definition,
                    saved_profile_id=saved.profile_id,
                    saved_profile_revision=saved.revision,
                )
            )
    if service.load_persisted_button_profile:
        saved_buttons = await asyncio.to_thread(button_profiles.get_selected_profile)
        if saved_buttons is not None:
            service.configure_initial_button_profile(
                saved_buttons.as_active(), saved_buttons.revision
            )
    service.mark_persistence_available()


async def _start_controller(service: ControllerLoop, publisher: LiveStatePublisher) -> None:
    await asyncio.to_thread(service.start, publisher.offer)
    await publisher.start()
    service.mark_ready()


async def _handle_initialization_failure(
    service: ControllerLoop,
    local_controls: LocalControlsService | None,
    failure: BaseException,
) -> None:
    service.mark_persistence_fault(str(failure))
    if local_controls is not None:
        await _try_set_local_condition(local_controls, CoordinatorCondition.FAULT)
        await asyncio.to_thread(local_controls.stop, graceful=False)


async def _handle_start_failure(
    service: ControllerLoop,
    publisher: LiveStatePublisher,
    local_controls: LocalControlsService | None,
) -> None:
    service.mark_not_ready()
    if local_controls is not None:
        await _try_set_local_condition(local_controls, CoordinatorCondition.FAULT)
    try:
        await _stop_controller(service, publisher)
    finally:
        if local_controls is not None:
            await asyncio.to_thread(local_controls.stop, graceful=False)


async def _shutdown(
    service: ControllerLoop,
    publisher: LiveStatePublisher,
    local_controls: LocalControlsService | None,
) -> None:
    service.mark_not_ready()
    failed = service.fatal
    if local_controls is not None:
        condition = (
            CoordinatorCondition.FAULT if failed else CoordinatorCondition.SHUTTING_DOWN
        )
        await _try_set_local_condition(local_controls, condition)
    try:
        await _stop_controller(service, publisher)
    finally:
        if local_controls is not None:
            await asyncio.to_thread(local_controls.stop, graceful=not failed)


async def _stop_controller(
    service: ControllerLoop,
    publisher: LiveStatePublisher,
) -> None:
    try:
        await asyncio.to_thread(service.stop, False)
    finally:
        try:
            if publisher.running:
                await publisher.stop()
        finally:
            await asyncio.to_thread(service.close_adapter)


async def _try_set_local_condition(
    service: LocalControlsService,
    condition: CoordinatorCondition,
) -> None:
    try:
        future = service.submit(CoordinatorConditionChanged(condition))
        await asyncio.wrap_future(future)
    except LocalControlsServiceError:
        # The local convenience subsystem cannot obstruct controller or publisher cleanup.
        pass
