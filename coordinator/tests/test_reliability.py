from __future__ import annotations

import threading
import time
from dataclasses import replace
from pathlib import Path

from e87canbus.api.main import create_app
from e87canbus.composition import build_live_controller_service
from e87canbus.config import CanNetwork, default_config
from e87canbus.features.settings_repository import SettingsStorageError
from e87canbus.runtime import CanReaderFailed, StateTopic
from e87canbus.service import ControllerServiceLifecycle
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
        controller_service=build_live_controller_service(config=disabled_live_config()),
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
        snapshot = app.state.controller_service.snapshot()
        assert snapshot.service.persistence.available is False
        assert snapshot.diagnostics.health.fatal is False


def test_reader_fatal_makes_service_unready_and_stops_owner(tmp_path: Path) -> None:
    app = create_app(
        controller_service=build_live_controller_service(config=disabled_live_config()),
        profile_database_path=tmp_path / "application.sqlite3",
    )

    with TestClient(app) as client:
        service = app.state.controller_service
        service.submit(CanReaderFailed(CanNetwork.KCAN, 1.0, "reader"))
        deadline = time.monotonic() + 1.0
        while service.lifecycle is not ControllerServiceLifecycle.STOPPED:
            assert time.monotonic() < deadline
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        assert service.fatal_exit_required is True
        assert service.snapshot().diagnostics.health.fatal is True


def test_live_composition_has_no_dev_routes_or_development_cors(tmp_path: Path) -> None:
    app = create_app(
        controller_service=build_live_controller_service(config=disabled_live_config()),
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
        assert not any(item.tx_enabled for item in app.state.controller_service.config.can_networks)


def test_built_frontend_is_served_same_origin(tmp_path: Path) -> None:
    frontend = tmp_path / "dist"
    (frontend / "assets").mkdir(parents=True)
    (frontend / "index.html").write_text("<h1>controller</h1>")
    (frontend / "assets" / "app.js").write_text("console.log('controller')")
    app = create_app(
        controller_service=build_live_controller_service(config=disabled_live_config()),
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
            controller_service=build_live_controller_service(config=disabled_live_config()),
            profile_database_path=database,
        )
        with TestClient(app) as client:
            assert client.get("/health/ready").status_code == 200
            boot_ids.append(app.state.controller_service.boot_id)

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
    can0_unit = (root / "deploy/systemd/e87canbus-can0.service").read_text()
    unit = (root / "deploy/systemd/e87canbus-controller.service").read_text()

    assert "Before=e87canbus-controller.service" in can0_unit
    assert "sys-subsystem-net-devices-can0.device" in can0_unit
    assert "restart-ms 100" in can0_unit
    assert "WantedBy=multi-user.target" in can0_unit
    assert "ExecStartPre=-/usr/sbin/ip link set can0 down" in can0_unit
    assert "ExecStart=/usr/sbin/ip link set can0 up" in can0_unit
    assert "ExecStop=-/usr/sbin/ip link set can0 down" in can0_unit
    assert "After=e87canbus-can0.service" in unit
    assert "EnvironmentFile=/etc/e87canbus/controller.env" in unit
    assert "e87canbus run --profile ${E87CANBUS_PROFILE}" in unit
    assert "Restart=on-failure" in unit
    assert "RestartSec=5s" in unit
    assert "--frontend-directory" in unit
    assert "tx" not in unit.lower()


def test_health_topic_is_closed_and_not_runtime_registered() -> None:
    assert StateTopic.HEALTH.value == "health"
    assert set(StateTopic) == {
        StateTopic.VEHICLE,
        StateTopic.ENGINE,
        StateTopic.STEERING,
        StateTopic.BUTTONS,
        StateTopic.LIGHTING,
        StateTopic.DEVICES,
        StateTopic.HEALTH,
    }
