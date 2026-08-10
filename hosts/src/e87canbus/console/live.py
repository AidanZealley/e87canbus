"""Bounded latest-state publication for the local console browser."""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

import socketio  # type: ignore[import-untyped]

from e87canbus.console.models import (
    CONSOLE_SNAPSHOT_EVENT,
    ConsoleCanState,
    ConsoleSnapshot,
    ConsoleSnapshotData,
)
from e87canbus.console.service import ConsoleCanService, ConsoleServiceSnapshot

LOGGER = logging.getLogger(__name__)


class ConsoleLivePublisher:
    """Coalesce frame activity while allowing a fault snapshot through promptly."""

    def __init__(
        self,
        sio: socketio.AsyncServer,
        service: ConsoleCanService,
        *,
        publication_interval_s: float = 1.0,
        send_timeout_s: float = 0.25,
    ) -> None:
        self._sio = sio
        self._service = service
        self._publication_interval_s = publication_interval_s
        self._send_timeout_s = send_timeout_s
        self._lock = threading.Lock()
        self._dirty = False
        self._urgent = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wake: asyncio.Event | None = None
        self._wake_scheduled = False
        self._task: asyncio.Task[None] | None = None
        self._stopping = False

    async def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("console live publisher may be started exactly once")
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="console-live-publisher")

    async def stop(self) -> None:
        self._stopping = True
        self._signal()
        task = self._task
        if task is not None:
            await task
        await self._sio.shutdown()
        self._task = None
        self._loop = None
        self._wake = None

    def offer(self, snapshot: ConsoleServiceSnapshot) -> None:
        with self._lock:
            self._dirty = True
            self._urgent = self._urgent or snapshot.fault is not None
        self._signal()

    async def send_snapshot(self, sid: str) -> None:
        await self._emit(self._service.snapshot(), to=sid)

    def _signal(self) -> None:
        with self._lock:
            loop = self._loop
            wake = self._wake
            if loop is None or wake is None or self._wake_scheduled:
                return
            self._wake_scheduled = True
        loop.call_soon_threadsafe(wake.set)

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        next_activity_publication = loop.time()
        while not self._stopping:
            with self._lock:
                dirty = self._dirty
                urgent = self._urgent
            now = loop.time()
            if dirty and (urgent or now >= next_activity_publication):
                with self._lock:
                    self._dirty = False
                    self._urgent = False
                await self._emit(self._service.snapshot())
                next_activity_publication = loop.time() + self._publication_interval_s
                continue

            wake = self._wake
            assert wake is not None
            timeout = max(next_activity_publication - now, 0.0) if dirty else None
            with suppress(TimeoutError):
                if timeout is None:
                    await wake.wait()
                else:
                    await asyncio.wait_for(wake.wait(), timeout=timeout)
            wake.clear()
            with self._lock:
                self._wake_scheduled = False

    async def _emit(self, snapshot: ConsoleServiceSnapshot, *, to: str | None = None) -> None:
        payload = ConsoleSnapshot(
            boot_id=snapshot.boot_id,
            revision=snapshot.revision,
            emitted_at=datetime.now(UTC),
            data=ConsoleSnapshotData(
                can=ConsoleCanState(
                    connected=snapshot.connected,
                    frames_received=snapshot.frames_received,
                    fault=snapshot.fault,
                )
            ),
        ).model_dump(mode="json")
        try:
            async with asyncio.timeout(self._send_timeout_s):
                await self._sio.emit(CONSOLE_SNAPSHOT_EVENT, payload, to=to)
        except Exception:
            LOGGER.warning("Console snapshot publication failed", exc_info=True)


def install_socket_handlers(
    sio: socketio.AsyncServer,
    publisher: ConsoleLivePublisher,
) -> None:
    @sio.event  # type: ignore[untyped-decorator]
    async def connect(sid: str, environ: dict[str, Any], auth: object) -> None:
        del environ, auth
        await publisher.send_snapshot(sid)
