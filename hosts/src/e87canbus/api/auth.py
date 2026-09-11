"""Authentication and closed authorization tables for coordinator transport."""

from __future__ import annotations

import asyncio
import base64
import binascii
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography import x509
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

INSTALLATION_ID_PATTERN = re.compile(r"^[a-z2-7]{52}$")
DEVICE_IDENTITY_PATTERN = re.compile(
    r"^urn:e87canbus:device:v1:(?P<installation>[a-z2-7]{52}):"
    r"(?P<role>[a-z][a-z0-9-]*):(?P<device>[0-9a-f-]{36})$"
)
CLIENT_VERIFY_HEADER = "x-e87-client-verify"
CLIENT_CERTIFICATE_HEADER = "x-e87-client-certificate"
OPERATOR_USERNAME = "operator"


class PrincipalKind(StrEnum):
    UNAUTHENTICATED = "unauthenticated"
    CONSOLE = "console"
    OPERATOR = "operator"


@dataclass(frozen=True, slots=True)
class Principal:
    kind: PrincipalKind
    installation_id: str | None = None
    device_id: str | None = None


UNAUTHENTICATED = Principal(PrincipalKind.UNAUTHENTICATED)
PUBLIC = frozenset(PrincipalKind)
CONSOLE_AND_OPERATOR = frozenset({PrincipalKind.CONSOLE, PrincipalKind.OPERATOR})
OPERATOR_ONLY = frozenset({PrincipalKind.OPERATOR})

# This table is the executable copy of the Wi-Fi device network contract. A route
# added elsewhere does not inherit console access.
HTTP_PERMISSIONS: dict[tuple[str, str], frozenset[PrincipalKind]] = {
    ("GET", "/health/live"): PUBLIC,
    ("GET", "/health/ready"): CONSOLE_AND_OPERATOR,
    ("GET", "/api/runtime"): CONSOLE_AND_OPERATOR,
    ("GET", "/api/settings"): CONSOLE_AND_OPERATOR,
    ("PUT", "/api/settings"): CONSOLE_AND_OPERATOR,
    ("PUT", "/api/steering/maximum-assistance"): CONSOLE_AND_OPERATOR,
    ("PUT", "/api/steering/mode"): CONSOLE_AND_OPERATOR,
    ("POST", "/api/steering/manual-assistance-adjustment"): CONSOLE_AND_OPERATOR,
    ("POST", "/api/steering/activate-profile"): CONSOLE_AND_OPERATOR,
    ("PUT", "/api/steering/manual-assistance-level"): CONSOLE_AND_OPERATOR,
    ("PUT", "/api/steering/curve"): CONSOLE_AND_OPERATOR,
    ("GET", "/api/steering/profiles"): CONSOLE_AND_OPERATOR,
    ("POST", "/api/steering/profiles"): CONSOLE_AND_OPERATOR,
    ("GET", "/api/steering/profile"): CONSOLE_AND_OPERATOR,
    ("GET", "/api/steering/profiles/{profile_id}"): CONSOLE_AND_OPERATOR,
    ("PUT", "/api/steering/profiles/{profile_id}"): CONSOLE_AND_OPERATOR,
    ("DELETE", "/api/steering/profiles/{profile_id}"): CONSOLE_AND_OPERATOR,
    ("GET", "/api/button-pad/profiles"): CONSOLE_AND_OPERATOR,
    ("POST", "/api/button-pad/profiles"): CONSOLE_AND_OPERATOR,
    ("GET", "/api/button-pad/profile"): CONSOLE_AND_OPERATOR,
    ("GET", "/api/button-pad/profiles/{profile_id}"): CONSOLE_AND_OPERATOR,
    ("PUT", "/api/button-pad/profiles/{profile_id}"): CONSOLE_AND_OPERATOR,
    ("DELETE", "/api/button-pad/profiles/{profile_id}"): CONSOLE_AND_OPERATOR,
    ("GET", "/api/system/provisioning"): OPERATOR_ONLY,
}

SOCKET_SEND_PERMISSIONS = {
    "controller.resync": CONSOLE_AND_OPERATOR,
    "trace.subscribe": CONSOLE_AND_OPERATOR,
    "trace.unsubscribe": CONSOLE_AND_OPERATOR,
}
# Publishers emit these events only to authenticated connections. Keep the receive
# allowlist explicit so a new live-contract event fails the authorization-table test.
SOCKET_RECEIVE_PERMISSIONS = {
    event: CONSOLE_AND_OPERATOR
    for event in (
        "controller.snapshot",
        "vehicle.state",
        "engine.state",
        "steering.state",
        "buttons.state",
        "lighting.state",
        "devices.state",
        "controller.health",
        "resources.changed",
        "trace.batch",
    )
}


class ApplicationAuthenticator:
    """Classify trusted proxy identities and operator Basic credentials."""

    def __init__(
        self,
        *,
        installation_id: str,
        operator_password_hash: str,
        trusted_proxy_addresses: frozenset[str] = frozenset({"127.0.0.1", "::1"}),
    ) -> None:
        if INSTALLATION_ID_PATTERN.fullmatch(installation_id) is None:
            raise ValueError("installation ID is invalid")
        if not operator_password_hash.startswith("$argon2id$"):
            raise ValueError("operator password hash is not Argon2id")
        self.installation_id = installation_id
        self._operator_password_hash = operator_password_hash
        self._trusted_proxy_addresses = trusted_proxy_addresses
        self._password_hasher = PasswordHasher()

    @classmethod
    def from_file(
        cls,
        *,
        installation_id: str,
        operator_password_hash_path: Path,
    ) -> ApplicationAuthenticator:
        try:
            password_hash = operator_password_hash_path.read_text(encoding="ascii").strip()
        except OSError:
            raise ValueError("operator password hash is unavailable") from None
        return cls(
            installation_id=installation_id,
            operator_password_hash=password_hash,
        )

    async def authenticate_request(self, request: Request) -> Principal:
        return await self._authenticate(
            client_address=request.client.host if request.client is not None else None,
            headers={key.lower(): value for key, value in request.headers.items()},
        )

    async def authenticate_environ(self, environ: dict[str, Any]) -> Principal:
        headers = {
            key.removeprefix("HTTP_").replace("_", "-").lower(): str(value)
            for key, value in environ.items()
            if key.startswith("HTTP_")
        }
        return await self._authenticate(
            client_address=_asgi_peer_address(environ),
            headers=headers,
        )

    async def _authenticate(
        self, *, client_address: str | None, headers: dict[str, str]
    ) -> Principal:
        certificate = headers.get(CLIENT_CERTIFICATE_HEADER)
        verified = headers.get(CLIENT_VERIFY_HEADER)
        if certificate is not None or verified == "SUCCESS":
            if client_address not in self._trusted_proxy_addresses or verified != "SUCCESS":
                return UNAUTHENTICATED
            return self._console_principal(certificate or "")

        credentials = _basic_credentials(headers.get("authorization"))
        if credentials is None or credentials[0] != OPERATOR_USERNAME:
            return UNAUTHENTICATED
        try:
            await asyncio.to_thread(
                self._password_hasher.verify,
                self._operator_password_hash,
                credentials[1],
            )
        except (InvalidHashError, VerificationError):
            return UNAUTHENTICATED
        return Principal(PrincipalKind.OPERATOR)

    def _console_principal(self, encoded_certificate: str) -> Principal:
        try:
            certificate = x509.load_pem_x509_certificate(unquote(encoded_certificate).encode())
            identities = certificate.extensions.get_extension_for_class(
                x509.SubjectAlternativeName
            ).value.get_values_for_type(x509.UniformResourceIdentifier)
        except (ValueError, UnicodeEncodeError, x509.ExtensionNotFound):
            return UNAUTHENTICATED
        if len(identities) != 1:
            return UNAUTHENTICATED
        match = DEVICE_IDENTITY_PATTERN.fullmatch(identities[0])
        if match is None or match["installation"] != self.installation_id:
            return UNAUTHENTICATED
        if match["role"] != PrincipalKind.CONSOLE:
            return UNAUTHENTICATED
        try:
            device_id = str(uuid.UUID(match["device"], version=4))
        except ValueError:
            return UNAUTHENTICATED
        if device_id != match["device"]:
            return UNAUTHENTICATED
        return Principal(PrincipalKind.CONSOLE, match["installation"], device_id)


class AuthorizationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, *, authenticator: ApplicationAuthenticator) -> None:
        super().__init__(app)
        self._authenticator = authenticator

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        principal = await self._authenticator.authenticate_request(request)
        permissions = http_permissions(request.method, request.url.path)
        if principal.kind not in permissions:
            status = 403 if principal.kind is not PrincipalKind.UNAUTHENTICATED else 401
            headers = {"WWW-Authenticate": 'Basic realm="e87canbus"'} if status == 401 else None
            return JSONResponse(
                status_code=status,
                content={"detail": "authentication required" if status == 401 else "forbidden"},
                headers=headers,
            )
        return await call_next(request)


def http_permissions(method: str, path: str) -> frozenset[PrincipalKind]:
    direct = HTTP_PERMISSIONS.get((method, path))
    if direct is not None:
        return direct
    if re.fullmatch(r"/api/(?:steering|button-pad)/profiles/[0-9a-f-]+", path):
        template = re.sub(r"/[0-9a-f-]+$", "/{profile_id}", path)
        return HTTP_PERMISSIONS.get((method, template), frozenset())
    if path.startswith("/api/dev/simulation/"):
        return OPERATOR_ONLY
    if path == "/socket.io" or path.startswith("/socket.io/"):
        return CONSOLE_AND_OPERATOR
    # The coordinator SPA is for the operator. Unknown API paths remain closed.
    if not path.startswith(("/api/", "/health/")):
        return OPERATOR_ONLY
    return frozenset()


def _asgi_peer_address(environ: dict[str, Any]) -> str | None:
    scope = environ.get("asgi.scope")
    if not isinstance(scope, Mapping):
        return None
    client = scope.get("client")
    if (
        not isinstance(client, (tuple, list))
        or len(client) != 2
        or not isinstance(client[0], str)
    ):
        return None
    return client[0]


def _basic_credentials(header: str | None) -> tuple[str, str] | None:
    if header is None:
        return None
    scheme, separator, encoded = header.partition(" ")
    if separator == "" or scheme.lower() != "basic":
        return None
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    username, separator, password = decoded.partition(":")
    return (username, password) if separator else None
