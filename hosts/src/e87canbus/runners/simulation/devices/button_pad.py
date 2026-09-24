"""One simulated button pad connected to the production device HTTP handlers."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import httpx2
from argon2 import PasswordHasher
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from fastapi import FastAPI
from pydantic import ValidationError
from starlette.types import Message, Scope

from e87canbus.api.auth import (
    CLIENT_CERTIFICATE_HEADER,
    CLIENT_VERIFY_HEADER,
    ApplicationAuthenticator,
    AuthorizationMiddleware,
)
from e87canbus.api.models.button_pad import ButtonPadConfigurationEnvelope, ButtonPadScene

LOGGER = logging.getLogger(__name__)
SIMULATED_INSTALLATION_ID = "a" * 52
SIMULATED_BUTTON_PAD_ID = "be1884de-0c8f-4b59-990c-5a2354c315f2"
STREAM_PATH = "/api/devices/configuration"
STREAM_IDLE_TIMEOUT_S = 35.0


@dataclass(frozen=True)
class AppliedButtonPadScene:
    generation: int
    scene: ButtonPadScene


class SimulatedButtonPad:
    def __init__(self, app: FastAPI, *, shutdown_timeout_s: float) -> None:
        self._headers = _verified_headers()
        authenticator = ApplicationAuthenticator(
            installation_id=SIMULATED_INSTALLATION_ID,
            operator_password_hash=PasswordHasher().hash("simulation-only"),
        )
        self._asgi = AuthorizationMiddleware(app, authenticator=authenticator)
        self._http = httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=self._asgi, client=("127.0.0.1", 0)),
            base_url="https://10.42.0.1",
            headers=self._headers,
            timeout=shutdown_timeout_s,
        )
        self._shutdown_timeout_s = shutdown_timeout_s
        self._applied: AppliedButtonPadScene | None = None
        self._ready = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def applied(self) -> AppliedButtonPadScene | None:
        current = self._applied
        if current is None:
            return None
        return AppliedButtonPadScene(current.generation, current.scene.model_copy(deep=True))

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="simulated-button-pad")
        try:
            await asyncio.wait_for(self._ready.wait(), self._shutdown_timeout_s)
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
        task = self._task
        self._task = None
        try:
            if task is not None:
                task.cancel()
                with suppress(TimeoutError):
                    await asyncio.wait_for(
                        asyncio.gather(task, return_exceptions=True), self._shutdown_timeout_s
                    )
        finally:
            await self._http.aclose()

    async def press(self, button_index: int) -> None:
        # An HTTP failure may follow a committed press. Never retry it.
        response = await self._http.post(
            "/api/devices/button-pad/presses", json={"button_index": button_index}
        )
        response.raise_for_status()
        if response.status_code != 204:
            raise RuntimeError(f"unexpected button-pad press status: {response.status_code}")

    async def _run(self) -> None:
        while True:
            try:
                await self._stream_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("simulated button-pad configuration stream failed")
            await asyncio.sleep(0.2)

    async def _stream_once(self) -> None:
        incoming: asyncio.Queue[Message] = asyncio.Queue(maxsize=1)
        outgoing: asyncio.Queue[Message] = asyncio.Queue(maxsize=2)
        incoming.put_nowait({"type": "http.request", "body": b"", "more_body": False})
        scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": STREAM_PATH,
            "raw_path": STREAM_PATH.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [(key.encode(), value.encode()) for key, value in self._headers.items()],
            "client": ("127.0.0.1", 0),
            "server": ("10.42.0.1", 443),
        }

        async def receive() -> Message:
            return await incoming.get()

        async def send(message: Message) -> None:
            await outgoing.put(message)

        request = asyncio.create_task(self._asgi(scope, receive, send))
        try:
            start = await asyncio.wait_for(
                _next_message(outgoing, request), STREAM_IDLE_TIMEOUT_S
            )
            if start["type"] != "http.response.start" or start["status"] != 200:
                raise RuntimeError(f"configuration stream rejected: {start}")
            headers = {key.lower(): value for key, value in start["headers"]}
            if not headers.get(b"content-type", b"").startswith(b"text/event-stream"):
                raise RuntimeError("configuration response is not SSE")
            if headers.get(b"cache-control") != b"no-store":
                raise RuntimeError("configuration response may be cached")
            pending = b""
            while True:
                message = await asyncio.wait_for(
                    _next_message(outgoing, request), STREAM_IDLE_TIMEOUT_S
                )
                if message["type"] != "http.response.body":
                    raise RuntimeError("unexpected configuration ASGI message")
                pending += message.get("body", b"")
                while b"\n\n" in pending:
                    record, pending = pending.split(b"\n\n", 1)
                    if len(record) > 1_048_576:
                        raise RuntimeError("configuration record exceeds 1 MiB")
                    if record.startswith(b"data: ") and b"\n" not in record:
                        await self._apply(record[6:])
                    elif not record.startswith(b":"):
                        raise RuntimeError("invalid configuration SSE record")
                if len(pending) > 1_048_576:
                    raise RuntimeError("configuration record exceeds 1 MiB")
                if not message.get("more_body", False):
                    return
        finally:
            # The route observes disconnect while the private request is still alive.
            if not incoming.full():
                incoming.put_nowait({"type": "http.disconnect"})
            request.cancel()
            with suppress(asyncio.CancelledError, TimeoutError):
                await asyncio.wait_for(request, self._shutdown_timeout_s)

    async def _apply(self, payload: bytes) -> None:
        try:
            envelope = ButtonPadConfigurationEnvelope.model_validate_json(payload)
        except (ValidationError, ValueError):
            current = self._applied
            if current is not None:
                await self._report(current.generation, "invalid configuration envelope")
            return
        self._applied = AppliedButtonPadScene(envelope.generation, envelope.configuration)
        await self._report(envelope.generation, None)
        self._ready.set()

    async def _report(self, generation: int, error: str | None) -> None:
        response = await self._http.post(
            "/api/devices/status",
            json={
                "status_version": 1,
                "applied_configuration_generation": generation,
                "configuration_error": error,
                "device": {},
            },
        )
        response.raise_for_status()
        if response.status_code != 204:
            raise RuntimeError(f"unexpected button-pad status response: {response.status_code}")


async def _next_message(
    outgoing: asyncio.Queue[Message], request: asyncio.Task[None]
) -> Message:
    queued = asyncio.create_task(outgoing.get())
    try:
        done, _ = await asyncio.wait({queued, request}, return_when=asyncio.FIRST_COMPLETED)
        if queued in done:
            return queued.result()
        await request
        raise RuntimeError("configuration stream ended")
    finally:
        queued.cancel()
        with suppress(asyncio.CancelledError):
            await queued


def _verified_headers() -> dict[str, str]:
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    identity = (
        f"urn:e87canbus:device:v1:{SIMULATED_INSTALLATION_ID}:"
        f"button-pad:{SIMULATED_BUTTON_PAD_ID}"
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "simulated-button-pad")]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "simulation")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.UniformResourceIdentifier(identity)]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    pem = certificate.public_bytes(serialization.Encoding.PEM).decode()
    return {CLIENT_VERIFY_HEADER: "SUCCESS", CLIENT_CERTIFICATE_HEADER: quote(pem, safe="")}
