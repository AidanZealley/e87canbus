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
from e87canbus.local_controls import CoordinatorCondition, CoordinatorConditionChanged
from e87canbus.local_controls.service import LocalControlsService, LocalControlsServiceError
from e87canbus.service import ControllerLoop, RuntimeExecution


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
            if database is not None:
                await asyncio.to_thread(database.initialize)
            stored_profiles = (
                await asyncio.to_thread(profiles.list_profiles)
                if service.load_persisted_steering_curve
                else ()
            )
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
            saved_buttons = (
                await asyncio.to_thread(button_profiles.get_selected_profile)
                if service.load_persisted_button_profile
                else None
            )
            if saved_buttons is not None:
                service.configure_initial_button_profile(
                    saved_buttons.as_active(), saved_buttons.revision
                )
            service.mark_persistence_available()
        except BaseException as exc:
            service.mark_persistence_fault(str(exc))
            if local_controls is not None:
                await _try_set_local_condition(local_controls, CoordinatorCondition.FAULT)
                await asyncio.to_thread(local_controls.stop, graceful=False)
            raise

        def publish(execution: RuntimeExecution) -> None:
            publisher.offer(execution)

        try:
            await asyncio.to_thread(service.start, publish)
            await publisher.start()
            service.mark_ready()
        except BaseException:
            service.mark_not_ready()
            if local_controls is not None:
                await _try_set_local_condition(local_controls, CoordinatorCondition.FAULT)
            try:
                await asyncio.to_thread(service.stop, False)
            finally:
                try:
                    if publisher.running:
                        await publisher.stop()
                finally:
                    await asyncio.to_thread(service.close_adapter)
                    if local_controls is not None:
                        await asyncio.to_thread(local_controls.stop, graceful=False)
            raise
        try:
            yield
        finally:
            service.mark_not_ready()
            failed = service.fatal
            if local_controls is not None:
                await _try_set_local_condition(
                    local_controls,
                    (
                        CoordinatorCondition.FAULT
                        if failed
                        else CoordinatorCondition.SHUTTING_DOWN
                    ),
                )
            try:
                await asyncio.to_thread(service.stop, False)
            finally:
                try:
                    await publisher.stop()
                finally:
                    try:
                        await asyncio.to_thread(service.close_adapter)
                    finally:
                        if local_controls is not None:
                            await asyncio.to_thread(
                                local_controls.stop,
                                graceful=not failed,
                            )

    return lifespan


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
