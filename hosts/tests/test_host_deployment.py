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


def test_only_role_specific_setup_entry_points_remain() -> None:
    assert not (SCRIPTS / "setup_pi.sh").exists()
    assert (SCRIPTS / "setup_coordinator.sh").stat().st_mode & 0o111
    assert (SCRIPTS / "setup_console.sh").stat().st_mode & 0o111

    coordinator = read(SCRIPTS / "setup_coordinator.sh")
    console = read(SCRIPTS / "setup_console.sh")
    assert "pnpm --filter ./apps/coordinator build" in coordinator
    assert "pnpm --filter ./apps/console build" in console
    assert "VITE_COORDINATOR_ORIGIN=http://10.43.0.1" in console
    assert "pnpm build" not in coordinator
    assert "pnpm build" not in console
    for obsolete in (
        SYSTEMD / "e87canbus-web-proxy.service",
        SYSTEMD / "e87canbus-web-proxy.socket",
        SYSTEMD / "e87canbus-kiosk.service",
        ROOT / "deploy/kiosk/e87canbus-kiosk.desktop",
        ROOT / "deploy/kiosk/start-kiosk.sh",
        ROOT / "deploy/udev/70-e87canbus-can.rules",
    ):
        assert not obsolete.exists()


def test_coordinator_installs_only_its_services_and_removes_the_old_kiosk() -> None:
    setup = read(SCRIPTS / "setup_coordinator.sh")

    for unit in (
        "e87canbus-controller.service",
        "e87canbus-kcan.service",
        "e87canbus-ptcan.service",
        "e87canbus-fcan.service",
        "e87canbus-coordinator-hotspot-proxy.socket",
        "e87canbus-coordinator-console-proxy.socket",
    ):
        assert unit in setup
    assert '"${REPO_ROOT}/deploy/systemd/e87canbus-console.service"' not in setup
    assert '"${REPO_ROOT}/deploy/systemd/e87canbus-console-kcan.service"' not in setup
    assert "systemctl enable --now e87canbus-console-kiosk" not in setup
    assert "Removing obsolete combined and console deployment files" in setup
    assert "/usr/local/bin/e87canbus-kiosk" in setup


def test_console_installs_only_receive_side_and_kiosk_services() -> None:
    setup = read(SCRIPTS / "setup_console.sh")

    for installed_path in (
        '"${REPO_ROOT}/deploy/systemd/e87canbus-console-kcan.service"',
        '"${REPO_ROOT}/deploy/systemd/e87canbus-console.service"',
        '"${REPO_ROOT}/deploy/systemd/e87canbus-console-kiosk.service"',
    ):
        assert installed_path in setup
    for forbidden_install in (
        '"${REPO_ROOT}/deploy/systemd/e87canbus-controller.service"',
        '"${REPO_ROOT}/deploy/systemd/e87canbus-ptcan.service"',
        '"${REPO_ROOT}/deploy/systemd/e87canbus-fcan.service"',
        '"${REPO_ROOT}/deploy/bin/e87canbus-hotspot"',
    ):
        assert forbidden_install not in setup
    assert "coordinator_panel_upload" not in setup
    assert "spi0.0" not in read(ROOT / "deploy/udev/70-e87canbus-console-can.rules")
    console_rules = read(ROOT / "deploy/udev/70-e87canbus-console-can.rules")
    assert 'KERNELS=="spi1.2"' not in console_rules


def test_both_applications_are_loopback_only_with_their_final_artifacts() -> None:
    controller = read(SYSTEMD / "e87canbus-controller.service")
    controller_env = read(SYSTEMD / "controller.env.example")
    console = read(SYSTEMD / "e87canbus-console.service")
    console_env = read(SYSTEMD / "console.env.example")

    assert "--host 127.0.0.1" in controller
    assert "--host 0.0.0.0" not in controller
    assert "frontend/apps/coordinator/dist" in controller_env
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
    assert "frontend/apps/console/dist" in console_env
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


def test_proxies_bind_only_the_two_coordinator_addresses() -> None:
    expected = {
        "hotspot": ("10.42.0.1:80", "wlan0"),
        "console": ("10.43.0.1:80", "eth0"),
    }
    for name, (address, interface) in expected.items():
        socket = read(SYSTEMD / f"e87canbus-coordinator-{name}-proxy.socket")
        service = read(SYSTEMD / f"e87canbus-coordinator-{name}-proxy.service")
        assert f"ListenStream={address}" in socket
        assert f"BindToDevice={interface}" in socket
        assert "ListenStream=0.0.0.0" not in socket
        assert "systemd-socket-proxyd 127.0.0.1:8000" in service


def test_console_link_has_fixed_non_routing_network_policy() -> None:
    coordinator = read(SCRIPTS / "setup_coordinator.sh")
    console = read(SCRIPTS / "setup_console.sh")
    common = read(SCRIPTS / "setup_host_common.sh")

    assert 'configure_console_link "10.43.0.1/30" 101' in coordinator
    assert 'configure_console_link "10.43.0.2/30" 101' in console
    assert 'ipv4.gateway ""' in common
    assert 'ipv4.dns ""' in common
    assert "ipv4.never-default yes" in common
    assert 'ipv4.routes "0.0.0.0/0 type=blackhole table=501"' in common
    assert 'ipv4.routing-rules "priority ${rule_priority} iif eth0 table 501"' in common
    assert "ipv4.method shared" not in common
    assert "ipv6.method disabled" in common


def test_console_can_is_exactly_one_listen_only_hat_controller() -> None:
    setup = read(SCRIPTS / "setup_console.sh")
    can_unit = read(SYSTEMD / "e87canbus-console-kcan.service")
    console_unit = read(SYSTEMD / "e87canbus-console.service")
    rules = read(ROOT / "deploy/udev/70-e87canbus-console-can.rules")

    assert "dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22" in setup
    assert "mcp2515,.*spi1-2" in setup  # removal only
    assert 'KERNELS=="spi1.1", NAME="kcan"' in rules
    assert rules.count("NAME=") == 1
    assert "bitrate 100000 listen-only on" in can_unit
    assert "listen-only off" not in can_unit
    assert "Before=e87canbus-console.service" in can_unit
    assert "After=e87canbus-console-kcan.service" in console_unit
    assert "Requires=e87canbus-console-kcan.service" in console_unit


def test_setup_scripts_validate_hardware_before_starting_applications() -> None:
    coordinator = read(SCRIPTS / "setup_coordinator.sh")
    console = read(SCRIPTS / "setup_console.sh")

    assert coordinator.index("require_pi_4") < coordinator.index(
        "systemctl restart e87canbus-controller.service"
    )
    assert coordinator.index("actual_spi_parent") < coordinator.index(
        "systemctl restart e87canbus-controller.service"
    )
    assert console.index("require_pi_4") < console.index(
        "systemctl restart e87canbus-console.service"
    )
    assert console.index("actual_spi_parent") < console.index(
        "systemctl restart e87canbus-console.service"
    )
    assert "EXPECTED_SPI_PARENTS=(spi0.0 spi1.1 spi1.2)" in coordinator
    assert '[[ "${actual_spi_parent}" == "${expected_spi_parent}" ]]' in coordinator
    assert '[[ "${actual_spi_parent}" != "spi1.1" ]]' in console


def test_all_deployment_shell_files_parse() -> None:
    paths = [*SCRIPTS.glob("*.sh"), *(ROOT / "deploy/bin").iterdir()]
    paths.extend((ROOT / "deploy/kiosk").glob("*.sh"))
    subprocess.run(["bash", "-n", *(str(path) for path in paths)], check=True)
