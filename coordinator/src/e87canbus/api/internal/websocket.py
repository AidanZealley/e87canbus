"""WebSocket connection and publication management."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from typing import Any

from fastapi import WebSocket

from e87canbus.simulation.engine import SimulatorSnapshot, snapshot_event

LOGGER = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self, send_timeout_s: float) -> None:
        self._connections: set[WebSocket] = set()
        self._publication_lock = asyncio.Lock()
        self._send_timeout_s = send_timeout_s

    async def connect(
        self,
        websocket: WebSocket,
        get_snapshot: Callable[[], SimulatorSnapshot],
    ) -> bool:
        async with self._publication_lock:
            await websocket.accept()
            try:
                await self._send_events(
                    websocket,
                    (snapshot_event(get_snapshot(), include_trace=True),),
                )
            except Exception:
                LOGGER.warning("removing failed simulator WebSocket", exc_info=True)
                return False
            self._connections.add(websocket)
            return True

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def send(self, websocket: WebSocket, event: dict[str, Any]) -> bool:
        async with self._publication_lock:
            try:
                await self._send_events(websocket, (event,))
            except Exception:
                LOGGER.warning("removing failed simulator WebSocket", exc_info=True)
                self.disconnect(websocket)
                return False
            return True

    async def broadcast(self, events: Sequence[dict[str, Any]]) -> None:
        async with self._publication_lock:
            disconnected: list[WebSocket] = []
            for websocket in tuple(self._connections):
                try:
                    await self._send_events(websocket, events)
                except Exception:
                    LOGGER.warning("removing failed simulator WebSocket", exc_info=True)
                    disconnected.append(websocket)
            for websocket in disconnected:
                self.disconnect(websocket)

    async def _send_events(
        self,
        websocket: WebSocket,
        events: Sequence[dict[str, Any]],
    ) -> None:
        async with asyncio.timeout(self._send_timeout_s):
            for event in events:
                await websocket.send_json(event)
