"""FastAPI lifecycle bridge for the unified controller service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from e87canbus.adapters.sqlite_database import SqliteApplicationDatabase
from e87canbus.adapters.sqlite_profiles import BUILT_IN_PROFILE_ID
from e87canbus.api.internal.live import LiveStatePublisher
from e87canbus.domain.profile_repository import SteeringProfileRepository
from e87canbus.domain.steering import initial_active_steering_curve
from e87canbus.service import ControllerService, RuntimeExecution


def create_lifespan(
    service: ControllerService,
    database: SqliteApplicationDatabase | None,
    profiles: SteeringProfileRepository,
    publisher: LiveStatePublisher,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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
            service.mark_persistence_available()
        except BaseException as exc:
            service.mark_persistence_fault(str(exc))
            raise

        def publish(execution: RuntimeExecution) -> None:
            publisher.offer(execution)

        try:
            await asyncio.to_thread(service.start, publish)
            await publisher.start()
            service.mark_ready()
        except BaseException:
            service.mark_not_ready()
            try:
                await asyncio.to_thread(service.stop, False)
            finally:
                try:
                    if publisher.running:
                        await publisher.stop()
                finally:
                    await asyncio.to_thread(service.close_adapter)
            raise
        try:
            yield
        finally:
            service.mark_not_ready()
            try:
                await asyncio.to_thread(service.stop, False)
            finally:
                try:
                    await publisher.stop()
                finally:
                    await asyncio.to_thread(service.close_adapter)

    return lifespan
