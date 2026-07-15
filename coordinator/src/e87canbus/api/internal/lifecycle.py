"""FastAPI lifecycle bridge for the unified controller service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from e87canbus.adapters.sqlite_database import SqliteApplicationDatabase
from e87canbus.api.internal.live import LiveStatePublisher
from e87canbus.service import ControllerService, RuntimeExecution


def create_lifespan(
    service: ControllerService,
    database: SqliteApplicationDatabase | None,
    publisher: LiveStatePublisher,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if database is not None:
            await asyncio.to_thread(database.initialize)
        publisher.set_legacy_manager(app.state.manager)
        await publisher.start()

        def publish(execution: RuntimeExecution) -> None:
            app.state.latest_snapshot = execution.compatibility_snapshot
            publisher.offer(execution)

        try:
            await asyncio.to_thread(service.start, publish)
        except BaseException:
            await publisher.stop()
            raise
        app.state.latest_snapshot = service.latest_compatibility_snapshot
        try:
            yield
        finally:
            try:
                await asyncio.to_thread(service.stop)
            finally:
                await publisher.stop()

    return lifespan
