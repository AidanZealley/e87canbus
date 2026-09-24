"""Exercise device configuration through the production ASGI response."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from e87canbus.adapters.sqlite_device_state import DeviceStateStorageError
from e87canbus.api.auth import DeviceRole
from e87canbus.api.internal import device_configuration
from e87canbus.api.main import create_app
from e87canbus.domain.buttons.profiles import (
    ActiveButtonProfile,
    ButtonSlot,
    button_profile_definition_with,
)
from e87canbus.domain.intents import ToggleAutomaticAssistance
from e87canbus.kernel import ActivateButtonProfile
from test_transport_authorization import (
    DEVICE_ID,
    authenticator,
    basic_headers,
    console_headers,
)


class AsgiRequest:
    def __init__(
        self, app: Any, headers: dict[str, str], *, fail_response_start: bool = False
    ) -> None:
        self.messages: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.incoming.put_nowait({"type": "http.request", "body": b"", "more_body": False})
        self.sent = 0
        self.release_sends = asyncio.Event()
        self.release_sends.set()
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/api/devices/configuration",
            "raw_path": b"/api/devices/configuration",
            "query_string": b"",
            "root_path": "",
            "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
            "client": ("127.0.0.1", 12345),
            "server": ("10.42.0.1", 443),
        }

        async def receive() -> dict[str, Any]:
            return await self.incoming.get()

        async def send(message: dict[str, Any]) -> None:
            self.sent += 1
            if fail_response_start and message["type"] == "http.response.start":
                raise OSError("client send failed")
            await self.release_sends.wait()
            await self.messages.put(message)

        self.task = asyncio.create_task(app(scope, receive, send))

    async def next(self) -> dict[str, Any]:
        return await asyncio.wait_for(self.messages.get(), 2)

    async def close(self) -> None:
        self.incoming.put_nowait({"type": "http.disconnect"})
        await asyncio.wait_for(self.task, 2)


def headers(message: dict[str, Any]) -> dict[str, str]:
    return {key.decode(): value.decode() for key, value in message["headers"]}


def record(message: dict[str, Any]) -> dict[str, Any]:
    body = message["body"].decode()
    assert body.startswith("data: ") and body.endswith("\n\n")
    assert body.count("\n") == 2
    return json.loads(body[6:-2])


@pytest.mark.asyncio
async def test_route_streams_current_and_replacement_with_exact_framing(tmp_path: Path) -> None:
    app = create_app(
        profile_database_path=tmp_path / "state.sqlite3",
        authenticator=authenticator(),
    )
    async with app.router.lifespan_context(app):
        request = AsgiRequest(app, console_headers(role="button-pad"))
        start = await request.next()
        assert start["status"] == 200
        assert headers(start)["content-type"] == "text/event-stream; charset=utf-8"
        assert headers(start)["cache-control"] == "no-store"
        initial = record(await request.next())
        assert initial["generation"] == 0
        assert len(initial["configuration"]["buttons"]) == 16
        assert app.state.device_configuration.subscriber_count == 1

        profile = ActiveButtonProfile(
            "test",
            button_profile_definition_with(
                {5: ButtonSlot(ToggleAutomaticAssistance(), (12, 34, 56))}
            ),
        )
        app.state.controller_loop.submit(ActivateButtonProfile(profile)).result(timeout=2)
        replacement = record(await request.next())
        assert replacement["generation"] == 1
        assert replacement["configuration"]["buttons"][5]["colour"] == [12, 34, 56]
        await request.close()
        assert app.state.device_configuration.subscriber_count == 0

        reconnect = AsgiRequest(app, console_headers(role="button-pad"))
        assert (await reconnect.next())["status"] == 200
        assert record(await reconnect.next()) == replacement
        await reconnect.close()
        assert app.state.device_state_repository.get_configuration(
            DEVICE_ID, DeviceRole.BUTTON_PAD
        ).generation == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("request_headers", "status"),
    [
        ({}, 401),
        (basic_headers(), 403),
        (console_headers(), 403),
        (console_headers(role="servotronic-controller"), 403),
        (console_headers(role="unknown-device"), 401),
    ],
)
async def test_only_button_pad_can_open_stream(
    tmp_path: Path, request_headers: dict[str, str], status: int
) -> None:
    app = create_app(
        profile_database_path=tmp_path / "state.sqlite3",
        authenticator=authenticator(),
    )
    async with app.router.lifespan_context(app):
        request = AsgiRequest(app, request_headers)
        assert (await request.next())["status"] == status
        await asyncio.wait_for(request.task, 2)
        assert app.state.device_configuration.subscriber_count == 0


@pytest.mark.asyncio
async def test_idle_stream_sends_comments_without_changing_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(device_configuration, "KEEPALIVE_INTERVAL_S", 0.01)
    app = create_app(
        profile_database_path=tmp_path / "state.sqlite3",
        authenticator=authenticator(),
    )
    async with app.router.lifespan_context(app):
        request = AsgiRequest(app, console_headers(role="button-pad"))
        assert (await request.next())["status"] == 200
        record(await request.next())
        assert (await request.next())["body"] == b": keepalive\n\n"
        assert app.state.device_state_repository.get_configuration(
            DEVICE_ID, DeviceRole.BUTTON_PAD
        ).generation == 0
        await request.close()


@pytest.mark.asyncio
async def test_lifespan_shutdown_closes_open_request(tmp_path: Path) -> None:
    app = create_app(
        profile_database_path=tmp_path / "state.sqlite3",
        authenticator=authenticator(),
    )
    async with app.router.lifespan_context(app):
        request = AsgiRequest(app, console_headers(role="button-pad"))
        assert (await request.next())["status"] == 200
        record(await request.next())
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(request.task, 2)
    assert app.state.device_configuration.subscriber_count == 0


@pytest.mark.asyncio
async def test_response_start_send_failure_unregisters_before_first_event(tmp_path: Path) -> None:
    app = create_app(
        profile_database_path=tmp_path / "state.sqlite3",
        authenticator=authenticator(),
    )
    async with app.router.lifespan_context(app):
        request = AsgiRequest(
            app, console_headers(role="button-pad"), fail_response_start=True
        )
        with pytest.raises(OSError, match="client send failed"):
            await asyncio.wait_for(request.task, 2)
        assert app.state.device_configuration.subscriber_count == 0


@pytest.mark.asyncio
async def test_publication_storage_failure_closes_stream_and_rejects_reconnect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(
        profile_database_path=tmp_path / "state.sqlite3",
        authenticator=authenticator(),
    )
    async with app.router.lifespan_context(app):
        request = AsgiRequest(app, console_headers(role="button-pad"))
        assert (await request.next())["status"] == 200
        record(await request.next())

        def fail_listing() -> None:
            raise DeviceStateStorageError("injected publication failure")

        monkeypatch.setattr(
            app.state.device_state_repository, "list_button_pad_configurations", fail_listing
        )
        profile = ActiveButtonProfile(
            "changed",
            button_profile_definition_with(
                {5: ButtonSlot(ToggleAutomaticAssistance(), (12, 34, 56))}
            ),
        )
        app.state.controller_loop.submit(ActivateButtonProfile(profile)).result(timeout=2)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(request.task, 2)
        assert app.state.device_configuration.subscriber_count == 0

        reconnect = AsgiRequest(app, console_headers(role="button-pad"))
        assert (await reconnect.next())["status"] == 500
        with pytest.raises(RuntimeError, match="not running"):
            await asyncio.wait_for(reconnect.task, 2)
        assert app.state.device_configuration.subscriber_count == 0


@pytest.mark.asyncio
async def test_saturated_send_cancels_request_and_releases_subscriber(tmp_path: Path) -> None:
    app = create_app(
        profile_database_path=tmp_path / "state.sqlite3",
        authenticator=authenticator(),
    )
    async with app.router.lifespan_context(app):
        request = AsgiRequest(app, console_headers(role="button-pad"))
        assert (await request.next())["status"] == 200
        record(await request.next())
        request.release_sends.clear()
        for index in range(8):
            profile = ActiveButtonProfile(
                f"profile-{index}",
                button_profile_definition_with(
                    {5: ButtonSlot(ToggleAutomaticAssistance(), (index + 1, 34, 56))}
                ),
            )
            app.state.controller_loop.submit(ActivateButtonProfile(profile)).result(timeout=2)
            async def generation_reached(target: int) -> None:
                while app.state.device_state_repository.get_configuration(
                    DEVICE_ID, DeviceRole.BUTTON_PAD
                ).generation < target:
                    await asyncio.sleep(0.005)
            await asyncio.wait_for(generation_reached(index + 1), 2)
            if index == 0:
                async def send_started() -> None:
                    while request.sent < 3:
                        await asyncio.sleep(0.005)
                await asyncio.wait_for(send_started(), 2)
        async def subscriber_removed() -> None:
            while app.state.device_configuration.subscriber_count:
                await asyncio.sleep(0.005)
        await asyncio.wait_for(subscriber_removed(), 2)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(request.task, 2)
        assert app.state.device_configuration.subscriber_count == 0
