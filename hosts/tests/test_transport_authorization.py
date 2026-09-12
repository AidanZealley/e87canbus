from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import quote

import pytest
import socketio  # type: ignore[import-untyped]
from argon2 import PasswordHasher
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from e87canbus.api.auth import (
    CLIENT_CERTIFICATE_HEADER,
    CLIENT_VERIFY_HEADER,
    HTTP_PERMISSIONS,
    SOCKET_RECEIVE_PERMISSIONS,
    SOCKET_SEND_PERMISSIONS,
    ApplicationAuthenticator,
    PrincipalKind,
)
from e87canbus.api.internal.live import install_socket_handlers
from e87canbus.api.main import create_app
from e87canbus.api.models.live_contract import ClientEvent, ServerEvent
from e87canbus.deployment import DeploymentProfile
from engineio.async_drivers.asgi import translate_request  # type: ignore[import-untyped]
from fastapi.testclient import TestClient

INSTALLATION_ID = "a" * 52
OTHER_INSTALLATION_ID = "b" * 52
DEVICE_ID = "12345678-1234-4234-9234-123456789abc"
PASSWORD = "test-only-operator-password"


def authenticator(*, trust_test_client: bool = False) -> ApplicationAuthenticator:
    trusted = (
        frozenset({"127.0.0.1", "::1", "testclient"})
        if trust_test_client
        else frozenset({"127.0.0.1", "::1"})
    )
    return ApplicationAuthenticator(
        installation_id=INSTALLATION_ID,
        operator_password_hash=PasswordHasher().hash(PASSWORD),
        trusted_proxy_addresses=trusted,
    )


def certificate_header(
    *, installation_id: str = INSTALLATION_ID, role: str = "console"
) -> str:
    private_key = ec.generate_private_key(ec.SECP256R1())
    identity = f"urn:e87canbus:device:v1:{installation_id}:{role}:{DEVICE_ID}"
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-device")]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-ca")]))
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(minutes=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.UniformResourceIdentifier(identity)]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    return quote(certificate.public_bytes(serialization.Encoding.PEM).decode(), safe="")


def console_headers(**identity: str) -> dict[str, str]:
    return {
        CLIENT_VERIFY_HEADER: "SUCCESS",
        CLIENT_CERTIFICATE_HEADER: certificate_header(**identity),
    }


def basic_headers(username: str = "operator", password: str = PASSWORD) -> dict[str, str]:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def status_document() -> dict[str, object]:
    return {
        "format_version": 1,
        "role": "coordinator",
        "installation_id": INSTALLATION_ID,
        "device_id": DEVICE_ID,
        "hostname": "e87-coordinator-test",
        "completed_phase": "complete",
        "artifact_digests": {"application": "c" * 64},
        "result": "succeeded",
        "error_code": None,
    }


def test_http_table_is_the_exact_console_allowlist() -> None:
    console_routes = {
        route
        for route, permissions in HTTP_PERMISSIONS.items()
        if PrincipalKind.CONSOLE in permissions
    }
    assert console_routes == {
        ("GET", "/health/live"),
        ("GET", "/health/ready"),
        ("GET", "/api/runtime"),
        ("GET", "/api/settings"),
        ("PUT", "/api/settings"),
        ("PUT", "/api/steering/maximum-assistance"),
        ("PUT", "/api/steering/mode"),
        ("POST", "/api/steering/manual-assistance-adjustment"),
        ("POST", "/api/steering/activate-profile"),
        ("PUT", "/api/steering/manual-assistance-level"),
        ("PUT", "/api/steering/curve"),
        ("GET", "/api/steering/profiles"),
        ("POST", "/api/steering/profiles"),
        ("GET", "/api/steering/profile"),
        ("GET", "/api/steering/profiles/{profile_id}"),
        ("PUT", "/api/steering/profiles/{profile_id}"),
        ("DELETE", "/api/steering/profiles/{profile_id}"),
        ("GET", "/api/button-pad/profiles"),
        ("POST", "/api/button-pad/profiles"),
        ("GET", "/api/button-pad/profile"),
        ("GET", "/api/button-pad/profiles/{profile_id}"),
        ("PUT", "/api/button-pad/profiles/{profile_id}"),
        ("DELETE", "/api/button-pad/profiles/{profile_id}"),
    }
    assert HTTP_PERMISSIONS[("GET", "/api/system/provisioning")] == {
        PrincipalKind.OPERATOR
    }


def test_http_table_accounts_for_every_production_operation(tmp_path: Path) -> None:
    schema = create_app(
        profile=DeploymentProfile.CAR,
        profile_database_path=tmp_path / "profiles.sqlite3",
    ).openapi()
    operations = {
        (method.upper(), path)
        for path, path_item in schema["paths"].items()
        for method in path_item
        if method in {"get", "post", "put", "delete"}
    }
    assert operations == set(HTTP_PERMISSIONS)


def test_socket_table_matches_the_closed_live_contract() -> None:
    assert set(SOCKET_SEND_PERMISSIONS) == set(ClientEvent)
    assert set(ServerEvent) == set(SOCKET_RECEIVE_PERMISSIONS)
    assert all(
        permissions == {PrincipalKind.CONSOLE, PrincipalKind.OPERATOR}
        for permissions in (
            *SOCKET_SEND_PERMISSIONS.values(),
            *SOCKET_RECEIVE_PERMISSIONS.values(),
        )
    )


def test_unauthenticated_client_gets_only_liveness(tmp_path: Path) -> None:
    app = create_app(
        profile=DeploymentProfile.CAR,
        profile_database_path=tmp_path / "profiles.sqlite3",
        authenticator=authenticator(trust_test_client=True),
    )
    client = TestClient(app)

    assert client.get("/health/live").json() == {"status": "live"}
    response = client.get("/api/runtime")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="e87canbus"'


def test_cors_handles_preflight_before_authorization(tmp_path: Path) -> None:
    origin = "http://127.0.0.1:8001"
    app = create_app(
        profile=DeploymentProfile.CAR,
        profile_database_path=tmp_path / "profiles.sqlite3",
        authenticator=authenticator(trust_test_client=True),
        cors_origins=(origin,),
    )
    response = TestClient(app).options(
        "/api/settings",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.asyncio
async def test_console_identity_uses_the_asgi_peer_and_requires_matching_identity() -> None:
    auth = authenticator()

    async def classify(remote: str, **identity: str) -> PrincipalKind:
        environ = await translated_socket_environ(
            remote,
            {
                **console_headers(**identity),
                "x-forwarded-for": "127.0.0.1",
            },
        )
        assert environ["REMOTE_ADDR"] == "127.0.0.1"
        principal = await auth.authenticate_environ(environ)
        return principal.kind

    assert await classify("127.0.0.1") is PrincipalKind.CONSOLE
    assert await classify("10.42.0.2") is PrincipalKind.UNAUTHENTICATED
    assert (
        await classify("127.0.0.1", installation_id=OTHER_INSTALLATION_ID)
        is PrincipalKind.UNAUTHENTICATED
    )
    assert await classify("127.0.0.1", role="coordinator") is PrincipalKind.UNAUTHENTICATED


def test_console_and_operator_http_permissions(tmp_path: Path) -> None:
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps(status_document()))
    app = create_app(
        profile=DeploymentProfile.CAR,
        profile_database_path=tmp_path / "profiles.sqlite3",
        authenticator=authenticator(trust_test_client=True),
        provisioning_status_path=status_path,
    )
    client = TestClient(app)

    assert client.get("/api/runtime", headers=console_headers()).status_code == 200
    assert client.get("/api/system/provisioning", headers=console_headers()).status_code == 403
    operator_headers = {**basic_headers(), CLIENT_VERIFY_HEADER: "NONE"}
    assert client.get("/api/runtime", headers=operator_headers).status_code == 200
    provisioning = client.get("/api/system/provisioning", headers=basic_headers())
    assert provisioning.json() == status_document()
    assert client.get("/api/runtime", headers=basic_headers(password="wrong")).status_code == 401


@pytest.mark.asyncio
async def test_socket_connection_authenticates_once_and_drops_failed_sessions() -> None:
    sio = socketio.AsyncServer(async_mode="asgi")
    send_snapshot = AsyncMock()
    publisher = SimpleNamespace(
        send_snapshot=send_snapshot,
        disconnect=lambda _sid: None,
        subscribe_trace=AsyncMock(),
        unsubscribe_trace=AsyncMock(),
    )
    install_socket_handlers(sio, publisher, authenticator())
    connect = sio.handlers["/"]["connect"]
    resync = sio.handlers["/"][ClientEvent.CONTROLLER_RESYNC]

    accepted = await translated_socket_environ("127.0.0.1", console_headers())
    spoofed = await translated_socket_environ("10.42.0.2", console_headers())
    assert await connect("accepted", accepted, None) is True
    assert await connect("rejected", spoofed, None) is False
    assert await connect("missing-scope", {"REMOTE_ADDR": "127.0.0.1"}, None) is False

    send_snapshot.side_effect = RuntimeError("snapshot failed")
    with pytest.raises(RuntimeError, match="snapshot failed"):
        await connect("snapshot-failed", accepted, None)
    send_snapshot.side_effect = None
    await resync("rejected")
    await resync("snapshot-failed")
    assert send_snapshot.await_count == 2


async def translated_socket_environ(
    peer_address: str, headers: dict[str, str]
) -> dict[str, object]:
    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "scheme": "ws",
        "server": ("127.0.0.1", 8000),
        "client": (peer_address, 45678),
        "root_path": "",
        "path": "/socket.io/",
        "raw_path": b"/socket.io/",
        "query_string": b"EIO=4&transport=websocket",
        "headers": [(key.encode(), value.encode()) for key, value in headers.items()],
    }

    async def receive() -> dict[str, str]:
        return {"type": "websocket.connect"}

    async def send(_message: object) -> None:
        return None

    return await translate_request(scope, receive, send)
