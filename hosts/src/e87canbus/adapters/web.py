"""Role-neutral ASGI helpers used by the host web applications."""

from __future__ import annotations

from pathlib import PurePosixPath

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHttpException
from starlette.responses import Response
from starlette.types import Scope


class SpaStaticFiles(StaticFiles):
    """Serve the built SPA entry for client routes while preserving asset 404s."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        server_prefixes = ("api", "health", "socket.io", "ws")
        first_segment = path.split("/", maxsplit=1)[0]
        fallback = (
            first_segment not in server_prefixes
            and first_segment != "assets"
            and PurePosixPath(path).suffix == ""
        )
        try:
            response = await super().get_response(path, scope)
        except StarletteHttpException as exc:
            if exc.status_code != 404 or not fallback:
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404 and fallback:
            return await super().get_response("index.html", scope)
        return response
