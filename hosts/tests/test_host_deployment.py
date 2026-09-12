from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from e87canbus.api.main import create_app
from e87canbus.deployment import DeploymentProfile
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
SYSTEMD = ROOT / "deploy/systemd"


def read(path: Path) -> str:
    return path.read_text()


def controller_origins() -> tuple[str, ...]:
    values = dict(
        line.split("=", maxsplit=1)
        for line in read(SYSTEMD / "controller.env.example").splitlines()
        if line and not line.startswith("#")
    )
    return (
        values["E87CANBUS_LOCALHOST_DEV_ORIGIN"],
        values["E87CANBUS_LOOPBACK_DEV_ORIGIN"],
        values["E87CANBUS_CONSOLE_ORIGIN"],
    )


def test_both_applications_are_loopback_only_with_their_final_artifacts() -> None:
    controller = read(SYSTEMD / "e87canbus-controller.service")
    controller_env = read(SYSTEMD / "controller.env.example")
    console = read(SYSTEMD / "e87canbus-console.service")
    console_env = read(SYSTEMD / "console.env.example")

    assert "--host 127.0.0.1" in controller
    assert "--host 0.0.0.0" not in controller
    assert "E87CANBUS_FRONTEND=/opt/e87canbus/current/frontend" in controller_env
    expected_origins = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    )
    assert controller_origins() == expected_origins
    assert controller.count("--cors-origin") == len(expected_origins)
    for variable in (
        "E87CANBUS_LOCALHOST_DEV_ORIGIN",
        "E87CANBUS_LOOPBACK_DEV_ORIGIN",
        "E87CANBUS_CONSOLE_ORIGIN",
    ):
        assert f"--cors-origin ${{{variable}}}" in controller

    assert "--host 127.0.0.1" in console
    assert "--host 0.0.0.0" not in console
    assert "E87CANBUS_CONSOLE_FRONTEND=/opt/e87canbus/current/frontend" in console_env
    kiosk = read(ROOT / "deploy/kiosk/start-console-kiosk.sh")
    assert "http://127.0.0.1:8000/health/live" in kiosk
    assert kiosk.rstrip().endswith("http://127.0.0.1:8000/")
    assert "10.43.0.1" not in kiosk


@pytest.mark.parametrize("origin", controller_origins())
def test_deployed_controller_origins_are_allowed_by_http_and_socketio(
    origin: str, tmp_path: Path
) -> None:
    origins = controller_origins()
    app = create_app(
        profile=DeploymentProfile.SIMULATOR,
        profile_database_path=tmp_path / "application.sqlite3",
        cors_origins=origins,
    )
    with TestClient(app) as client:
        response = client.options(
            "/api/settings",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        socket_response = client.get(
            "/socket.io/?EIO=4&transport=polling",
            headers={"Origin": origin},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert socket_response.status_code == 200


def test_deployed_controller_rejects_an_unrelated_origin(tmp_path: Path) -> None:
    origins = controller_origins()
    app = create_app(
        profile=DeploymentProfile.SIMULATOR,
        profile_database_path=tmp_path / "application.sqlite3",
        cors_origins=origins,
    )
    with TestClient(app) as client:
        response = client.options(
            "/api/settings",
            headers={
                "Origin": "http://untrusted.invalid",
                "Access-Control-Request-Method": "GET",
            },
        )
        socket_response = client.get(
            "/socket.io/?EIO=4&transport=polling",
            headers={"Origin": "http://untrusted.invalid"},
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
    assert socket_response.status_code == 400


def test_console_can_is_one_profile_controlled_hat_controller() -> None:
    can_unit = read(SYSTEMD / "e87canbus-console-kcan.service")
    console_env = read(SYSTEMD / "console.env.example")
    console_unit = read(SYSTEMD / "e87canbus-console.service")
    rules = read(ROOT / "deploy/udev/70-e87canbus-console-can.rules")

    assert 'KERNELS=="spi1.1", NAME="kcan"' in rules
    assert rules.count("NAME=") == 1
    assert "bitrate 100000 listen-only ${E87CANBUS_CONSOLE_CAN_LISTEN_ONLY}" in can_unit
    assert "EnvironmentFile=/etc/e87canbus/console.env" in can_unit
    assert "E87CANBUS_CONSOLE_CAN_LISTEN_ONLY=on" in console_env
    assert "Before=e87canbus-console.service" in can_unit
    assert "After=e87canbus-console-kcan.service" in console_unit
    assert "Requires=e87canbus-console-kcan.service" in console_unit


def test_all_deployment_shell_files_parse() -> None:
    paths = [*SCRIPTS.glob("*.sh"), *(ROOT / "deploy/bin").iterdir()]
    paths.extend((ROOT / "deploy/kiosk").glob("*.sh"))
    subprocess.run(["bash", "-n", *(str(path) for path in paths)], check=True)
