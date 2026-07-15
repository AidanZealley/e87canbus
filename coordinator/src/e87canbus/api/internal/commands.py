"""Typed HTTP-to-controller command ownership seam."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future

from fastapi import FastAPI

from e87canbus.api.errors import ApiProblem
from e87canbus.api.models.commands import CommandAcknowledgement
from e87canbus.service import (
    ControllerInboxFull,
    ControllerServiceNotRunning,
    ControllerWorkUnavailable,
)


async def submit_runtime_work(app: FastAPI, work: object) -> int:
    """Submit once and await finitely through the service ownership seam."""

    service = app.state.controller_service
    try:
        future: Future[int] = service.submit(work)
    except ControllerInboxFull as exc:
        raise ApiProblem(503, "runtime_queue_full", "controller runtime inbox is full") from exc
    except ControllerServiceNotRunning as exc:
        raise ApiProblem(503, "controller_unavailable", str(exc)) from exc

    try:
        result = await asyncio.wait_for(
            asyncio.shield(asyncio.wrap_future(future)),
            timeout=service.config.runtime_command_timeout_s,
        )
    except TimeoutError as exc:
        raise ApiProblem(
            503,
            "command_timeout",
            "controller command did not complete before the response timeout",
        ) from exc
    except ControllerWorkUnavailable as exc:
        raise ApiProblem(503, "controller_failed", str(exc)) from exc
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc
    except Exception as exc:
        raise ApiProblem(
            503,
            "controller_runtime_error",
            "controller command failed during processing",
        ) from exc

    return result


async def submit_command(app: FastAPI, command: object) -> CommandAcknowledgement:
    """Submit semantic intent and acknowledge the resulting boot/revision."""

    revision = await submit_runtime_work(app, command)
    service = app.state.controller_service
    return CommandAcknowledgement(
        boot_id=service.boot_id,
        revision=revision,
    )
