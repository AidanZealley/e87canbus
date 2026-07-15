"""FastAPI lifecycle bridge for the unified controller service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from e87canbus.adapters.sqlite_database import SqliteApplicationDatabase
from e87canbus.service import ControllerService, RuntimeExecution


def create_lifespan(
    service: ControllerService,
    database: SqliteApplicationDatabase | None,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if database is not None:
            await asyncio.to_thread(database.initialize)
        loop = asyncio.get_running_loop()

        def publish(execution: RuntimeExecution) -> None:
            app.state.latest_snapshot = execution.compatibility_snapshot
            if not execution.events:
                return
            publication = asyncio.run_coroutine_threadsafe(
                app.state.manager.broadcast(execution.events),
                loop,
            )
            publication.result()

        await asyncio.to_thread(service.start, publish)
        app.state.latest_snapshot = service.latest_compatibility_snapshot
        try:
            yield
        finally:
            await asyncio.to_thread(service.stop)

    return lifespan
