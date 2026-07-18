"""Shared HTTP error contract for the API."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from e87canbus.api.models.errors import ApiProblemCode, ApiProblemResponse

PROBLEM_RESPONSE: dict[str, Any] = {"model": ApiProblemResponse}


def api_problem_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Describe the shared problem envelope for the supplied status codes."""

    return {status_code: PROBLEM_RESPONSE for status_code in status_codes}


class ApiProblem(Exception):
    def __init__(
        self,
        status_code: int,
        code: ApiProblemCode,
        message: str,
        *,
        current_revision: int | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.current_revision = current_revision


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def api_problem_handler(request: Request, exc: ApiProblem) -> JSONResponse:
        if exc.code in {"settings_storage_error", "profile_storage_error"}:
            request.app.state.controller_service.mark_persistence_fault(exc.message)
        error: dict[str, Any] = {"code": exc.code, "message": exc.message}
        if exc.current_revision is not None:
            error["current_revision"] = exc.current_revision
        return JSONResponse(status_code=exc.status_code, content={"error": error})

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        issues = [
            {"location": list(issue["loc"]), "message": issue["msg"], "type": issue["type"]}
            for issue in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "request validation failed",
                    "issues": issues,
                }
            },
        )
