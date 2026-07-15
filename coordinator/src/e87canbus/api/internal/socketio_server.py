"""Socket.IO server composition with finite per-client Engine.IO queues."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import engineio  # type: ignore[import-untyped]
import socketio  # type: ignore[import-untyped]


class SaturatingBoundedQueue(asyncio.Queue[Any]):
    """Finite Engine.IO queue that aborts a peer instead of blocking or losing packets."""

    def __init__(
        self,
        capacity: int,
        on_saturated: Callable[[asyncio.Queue[Any]], Awaitable[None]],
    ) -> None:
        if capacity < 1:
            raise ValueError("Engine.IO outbound queue capacity must be positive")
        super().__init__(maxsize=capacity)
        self._on_saturated = on_saturated

    async def put(self, item: Any) -> None:
        try:
            super().put_nowait(item)
        except asyncio.QueueFull:
            await self._on_saturated(self)


class BoundedEngineIoServer(engineio.AsyncServer):  # type: ignore[misc]
    def __init__(self, *args: Any, outbound_queue_capacity: int, **kwargs: Any) -> None:
        if outbound_queue_capacity < 1:
            raise ValueError("Engine.IO outbound queue capacity must be positive")
        self.outbound_queue_capacity = outbound_queue_capacity
        self.outbound_queue_saturations = 0
        super().__init__(*args, **kwargs)

    def create_queue(self, *args: Any, **kwargs: Any) -> asyncio.Queue[Any]:
        if args or kwargs:
            raise TypeError("bounded Engine.IO queues use the configured capacity")
        return SaturatingBoundedQueue(
            self.outbound_queue_capacity,
            self._disconnect_saturated_peer,
        )

    async def _disconnect_saturated_peer(self, queue: asyncio.Queue[Any]) -> None:
        saturated = next(
            (
                (sid, peer)
                for sid, peer in self.sockets.items()
                if peer.queue is queue
            ),
            None,
        )
        if saturated is None:
            return
        sid, peer = saturated
        self.outbound_queue_saturations += 1
        self.logger.warning(
            "Disconnecting slow peer %s after its outbound queue reached %d packets",
            sid,
            self.outbound_queue_capacity,
        )
        await peer.close(
            wait=False,
            abort=True,
            reason=self.reason.SERVER_DISCONNECT,
        )
        self.sockets.pop(sid, None)


class BoundedSocketIoServer(socketio.AsyncServer):  # type: ignore[misc]
    def _engineio_server_class(self) -> type[BoundedEngineIoServer]:
        return BoundedEngineIoServer
