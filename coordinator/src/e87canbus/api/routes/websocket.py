"""Live API event-stream route."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["events"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    app = websocket.app
    connected = await app.state.manager.connect(websocket, lambda: app.state.latest_snapshot)
    if not connected:
        return
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping" and not await app.state.manager.send(
                websocket, {"type": "heartbeat"}
            ):
                return
    except WebSocketDisconnect:
        app.state.manager.disconnect(websocket)
