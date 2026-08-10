from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import replace
from pathlib import Path

from e87canbus.api.main import create_app
from e87canbus.config import CanNetwork, default_config
from e87canbus.domain.settings.repository import SettingsStorageError
from e87canbus.kernel import CanReaderFailed
from e87canbus.runners.composition import build_live_controller_loop
from e87canbus.service import ControllerLoopLifecycle
from fastapi.testclient import TestClient


class FailingSettingsRepository:
    def get_settings(self):
        raise SettingsStorageError("database unavailable")

    def update_settings(self, expected_revision, candidate):
        del expected_revision, candidate
        raise SettingsStorageError("database unavailable")


class EmptyProfileRepository:
    def list_profiles(self):
        return ()

    def get_profile(self, profile_id):
        del profile_id
        return None

    def create_profile(self, name, definition):
        raise AssertionError((name, definition))

    def update_profile(self, profile_id, expected_revision, name, definition):
        raise AssertionError((profile_id, expected_revision, name, definition))

    def delete_profile(self, profile_id, expected_revision):
        raise AssertionError((profile_id, expected_revision))


def disabled_live_config():
    config = default_config()
    return replace(
        config,
        can_networks=tuple(replace(item, enabled=False) for item in config.can_networks),
        tick_interval_s=60.0,
    )


def test_sqlite_outage_rejects_resource_and_leaves_live_controller_responsive() -> None:
    app = create_app(
        controller_loop=build_live_controller_loop(config=disabled_live_config()),
        profile_repository=EmptyProfileRepository(),
        settings_repository=FailingSettingsRepository(),
    )

    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 200
        failed = client.get("/api/settings")
        assert failed.status_code == 503
        assert failed.json()["error"]["code"] == "settings_storage_error"
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        snapshot = app.state.controller_loop.snapshot()
        assert snapshot.service.persistence.available is False
        assert snapshot.diagnostics.health.fatal is False


def test_reader_fatal_makes_service_unready_and_stops_owner(tmp_path: Path) -> None:
    app = create_app(
        controller_loop=build_live_controller_loop(config=disabled_live_config()),
        profile_database_path=tmp_path / "application.sqlite3",
    )

    with TestClient(app) as client:
        service = app.state.controller_loop
        service.submit(CanReaderFailed(CanNetwork.KCAN, 1.0, "reader"))
        deadline = time.monotonic() + 1.0
        while service.lifecycle is not ControllerLoopLifecycle.STOPPED:
            assert time.monotonic() < deadline
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        assert service.fatal_exit_required is True
        assert service.snapshot().diagnostics.health.fatal is True


def test_live_composition_has_no_dev_routes_or_development_cors(tmp_path: Path) -> None:
    app = create_app(
        controller_loop=build_live_controller_loop(config=disabled_live_config()),
        profile_database_path=tmp_path / "application.sqlite3",
    )
    with TestClient(app) as client:
        assert client.post("/api/dev/simulation/reset").status_code == 404
        response = client.options(
            "/api/settings",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
        assert not any(item.tx_enabled for item in app.state.controller_loop.config.can_networks)


def test_built_frontend_is_served_same_origin(tmp_path: Path) -> None:
    frontend = tmp_path / "dist"
    (frontend / "assets").mkdir(parents=True)
    (frontend / "index.html").write_text("<h1>controller</h1>")
    (frontend / "assets" / "app.js").write_text("console.log('controller')")
    app = create_app(
        controller_loop=build_live_controller_loop(config=disabled_live_config()),
        profile_database_path=tmp_path / "application.sqlite3",
        frontend_directory=frontend,
    )
    with TestClient(app) as client:
        assert client.get("/").text == "<h1>controller</h1>"
        assert client.get("/dev").text == "<h1>controller</h1>"
        assert client.get("/car").text == "<h1>controller</h1>"
        assert client.get("/assets/app.js").text == "console.log('controller')"
        assert client.get("/assets/missing.js").status_code == 404
        assert client.get("/api/health").status_code == 404
        assert client.get("/api/unknown").status_code == 404
        assert client.get("/ws").status_code == 404
        assert client.get("/health/unknown").status_code == 404
        assert client.get("/health/ready").status_code == 200


def test_repeated_lifecycle_releases_threads_tasks_and_database_locks(tmp_path: Path) -> None:
    baseline = {thread.ident for thread in threading.enumerate()}
    database = tmp_path / "application.sqlite3"
    boot_ids: list[str] = []

    for _ in range(5):
        app = create_app(
            controller_loop=build_live_controller_loop(config=disabled_live_config()),
            profile_database_path=database,
        )
        with TestClient(app) as client:
            assert client.get("/health/ready").status_code == 200
            boot_ids.append(app.state.controller_loop.boot_id)

    remaining = {
        thread.ident
        for thread in threading.enumerate()
        if thread.name in {"controller-owner", "controller-fatal-monitor"}
    }
    assert remaining.issubset(baseline)
    assert len(set(boot_ids)) == 5
    database.rename(tmp_path / "moved.sqlite3")


def test_systemd_unit_runs_canonical_rx_only_service_with_bounded_restart() -> None:
    root = Path(__file__).resolve().parents[2]
    # The interface names and bitrates come from the coordinator's own configuration, so a
    # rename has to reach the units and udev rules to pass.
    networks = default_config().can_networks
    can_units = {
        network.interface: (
            root / f"deploy/systemd/e87canbus-{network.interface}.service"
        ).read_text()
        for network in networks
    }
    unit = (root / "deploy/systemd/e87canbus-controller.service").read_text()

    for network in networks:
        interface = network.interface
        can_unit = can_units[interface]
        assert "Before=e87canbus-controller.service" in can_unit
        assert f"sys-subsystem-net-devices-{interface}.device" in can_unit
        assert "restart-ms 100" in can_unit
        assert "WantedBy=multi-user.target" in can_unit
        assert "RequiredBy=e87canbus-controller.service" in can_unit
        assert f"ExecStartPre=-/usr/sbin/ip link set {interface} down" in can_unit
        assert f"ExecStart=/usr/sbin/ip link set {interface} up" in can_unit
        assert f"ExecStop=-/usr/sbin/ip link set {interface} down" in can_unit
        assert f"bitrate {network.bitrate}" in can_unit
    ordering = next(line for line in unit.splitlines() if line.startswith("After=e87canbus-"))
    for interface in can_units:
        assert f"e87canbus-{interface}.service" in ordering
    assert "EnvironmentFile=/etc/e87canbus/controller.env" in unit
    assert "e87canbus run --profile ${E87CANBUS_PROFILE}" in unit
    assert "Restart=on-failure" in unit
    assert "RestartSec=5s" in unit
    assert "--frontend-directory" in unit


def test_pi_setup_owns_and_validates_the_complete_three_channel_can_stack() -> None:
    root = Path(__file__).resolve().parents[2]
    setup = (root / "scripts/setup_pi.sh").read_text()

    assert "dtoverlay=spi1-3cs" in setup
    assert "dtoverlay=uart3" in setup
    assert 'PANEL_UART_DEVICE="/dev/ttyAMA3"' in setup
    assert (
        "dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000"
        in setup
    )
    assert (
        "dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22,speed=10000000"
        in setup
    )
    assert (
        "dtoverlay=mcp2515,spi1-2,oscillator=16000000,interrupt=13,speed=10000000"
        in setup
    )
    assert "disable_splash=1" in setup

    interfaces = [network.interface for network in default_config().can_networks]
    assert f"CAN_INTERFACES=({' '.join(interfaces)})" in setup
    assert "EXPECTED_SPI_PARENTS=(spi0.0 spi1.1 spi1.2)" in setup
    for interface in interfaces:
        assert f"e87canbus-{interface}.service" in setup

    # Each controller keeps the name its configuration expects, in SPI connection order.
    naming_rules = (root / "deploy/udev/70-e87canbus-can.rules").read_text()
    for spi_parent, interface in zip(("spi0.0", "spi1.1", "spi1.2"), interfaces, strict=True):
        assert f'KERNELS=="{spi_parent}", NAME="{interface}"' in naming_rules


def test_hotspot_helper_exposes_only_the_fixed_runtime_operations() -> None:
    root = Path(__file__).resolve().parents[2]
    helper_path = root / "deploy/bin/e87canbus-hotspot"
    helper = helper_path.read_text()
    sudoers = (root / "deploy/sudoers/e87canbus-hotspot").read_text()
    unit = (root / "deploy/systemd/e87canbus-controller.service").read_text()

    assert helper_path.stat().st_mode & 0o111
    assert "/usr/bin/nmcli --wait 0 connection up id e87canbus-hotspot" in helper
    assert "/usr/bin/nmcli connection down id e87canbus-hotspot" in helper
    assert "/usr/bin/nmcli --get-values GENERAL.STATE" in helper
    assert "/usr/sbin/iw dev wlan0 station dump" in helper

    helper_command = "/usr/local/libexec/e87canbus-hotspot"
    # The count is the closure property: the loop below proves the four intended actions
    # are granted, and this proves there is no fifth grant alongside them.
    assert sudoers.count(helper_command) == 4
    assert "nmcli" not in sudoers
    assert "/usr/sbin/iw" not in sudoers
    assert "*" not in sudoers
    for action in ("activate", "deactivate", "state", "stations"):
        assert f"{helper_command} {action}" in sudoers
    assert "NoNewPrivileges=false" in unit

    for arguments in ((), ("invalid",), ("state", "extra")):
        result = subprocess.run(
            (helper_path, *arguments),
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2


def test_headless_kiosk_activates_and_owns_its_virtual_terminal() -> None:
    """Pin the VT ownership settings that took a long bench session to find.

    These greps look like transcription, and they are, but each line here is a fix for
    an observed failure on the target: cage times out on an inactive VT, and the HDMI
    CEC pointer draws a cursor over the touchscreen. Deleting one is easy to do by
    accident and the failure only shows up on the Pi.
    """
    root = Path(__file__).resolve().parents[2]
    unit = (root / "deploy/systemd/e87canbus-kiosk.service").read_text()
    input_rules = (root / "deploy/udev/71-e87canbus-kiosk-input.rules").read_text()

    assert 'ATTRS{name}=="vc4-hdmi-*"' in input_rules
    assert 'ENV{LIBINPUT_IGNORE_DEVICE}="1"' in input_rules
    assert "Conflicts=getty@tty7.service" in unit
    assert "TTYPath=/dev/tty7" in unit
    assert "TTYReset=yes" in unit
    assert "TTYVHangup=yes" in unit
    assert "TTYVTDisallocate=yes" in unit
    assert "StandardInput=tty-fail" in unit
    assert "StandardOutput=journal" in unit
    assert "StandardError=journal" in unit
    assert "ExecStartPre=+/usr/bin/chvt 7" in unit

