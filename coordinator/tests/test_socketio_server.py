from __future__ import annotations

import engineio  # type: ignore[import-untyped]
import pytest
from e87canbus.api.internal.socketio_server import BoundedEngineIoServer
from engineio import packet  # type: ignore[import-untyped]
from engineio.async_socket import AsyncSocket  # type: ignore[import-untyped]


@pytest.mark.asyncio
async def test_engineio_peer_queue_is_finite_and_saturation_aborts_peer() -> None:
    server = BoundedEngineIoServer(
        async_mode="asgi",
        outbound_queue_capacity=2,
    )
    peer = AsyncSocket(server, "slow-peer")
    server.sockets[peer.sid] = peer

    await peer.send(packet.Packet(packet.MESSAGE, data="first"))
    await peer.send(packet.Packet(packet.MESSAGE, data="second"))
    await peer.send(packet.Packet(packet.MESSAGE, data="would-overflow"))

    assert peer.queue.maxsize == 2
    assert peer.queue.qsize() == 2
    assert peer.closed is True
    assert peer.sid not in server.sockets
    assert server.outbound_queue_saturations == 1


def test_installed_engineio_default_queue_is_unbounded() -> None:
    server = engineio.AsyncServer(async_mode="asgi")

    assert server.create_queue().maxsize == 0
