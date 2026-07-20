from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

import pytest
from e87canbus.api.main import create_app
from e87canbus.composition import (
    build_controller_service,
    build_live_controller_service,
    build_simulated_controller_service,
)
from e87canbus.config import CanNetwork, default_config
from e87canbus.deployment import (
    CanTransport,
    DeploymentProfile,
    SimulationApiScope,
    VehicleSource,
    deployment_spec,
)
from e87canbus.device import DeviceRole, DeviceSource
from e87canbus.protocol.can import CanFrame
from e87canbus.runtime import ReceivedCanFrame
from e87canbus.simulation.protocol import encode_simulated_speed
from fastapi.testclient import TestClient


class FakeSocketCanBus:
    def __init__(self, interface: str) -> None:
        self.interface = interface

    def send(self, frame: CanFrame) -> None:
        del frame

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        time.sleep(min(timeout_s or 0.0, 0.001))
        return None

    def shutdown(self) -> None:
        pass


def slow_config():
    return replace(default_config(), tick_interval_s=60.0)


def test_car_profile_is_physical_and_has_no_simulation_capabilities() -> None:
    spec = deployment_spec(DeploymentProfile.CAR)

    assert spec.transport is CanTransport.SOCKETCAN
    assert spec.vehicle_source is VehicleSource.PHYSICAL
    assert spec.device_source(DeviceRole.BUTTON_PAD) is DeviceSource.PHYSICAL
    assert spec.simulation_api is SimulationApiScope.NONE
    assert spec.tx_grants == frozenset()


def test_closed_profile_fields_cannot_be_recombined() -> None:
    with pytest.raises(ValueError, match="closed composition"):
        replace(
            deployment_spec(DeploymentProfile.CAR),
            vehicle_source=VehicleSource.EMULATED,
        )


def test_runtime_transport_must_match_the_deployment_profile() -> None:
    with pytest.raises(ValueError, match="SocketCAN deployment"):
        build_live_controller_service(deployment=deployment_spec(DeploymentProfile.SIMULATOR))
    with pytest.raises(ValueError, match="in-memory deployment"):
        build_simulated_controller_service(deployment=deployment_spec(DeploymentProfile.CAR))


def test_bench_profile_is_physical_kcan_with_only_virtual_vehicle_controls() -> None:
    spec = deployment_spec(DeploymentProfile.BENCH)

    assert spec.transport is CanTransport.SOCKETCAN
    assert spec.physical_networks == {CanNetwork.KCAN}
    assert spec.vehicle_source is VehicleSource.EMULATED
    assert spec.device_source(DeviceRole.BUTTON_PAD) is DeviceSource.PHYSICAL
    assert spec.device_source(DeviceRole.SERVOTRONIC_CONTROLLER) is DeviceSource.DISABLED
    assert spec.simulation_api is SimulationApiScope.VEHICLE


def test_bench_api_accepts_vehicle_telemetry_but_omits_other_simulation_controls(
    tmp_path: Path,
) -> None:
    service = build_controller_service(
        DeploymentProfile.BENCH,
        config=slow_config(),
        socketcan_factory=FakeSocketCanBus,
    )
    app = create_app(
        controller_service=service,
        profile_database_path=tmp_path / "bench.sqlite3",
    )

    with TestClient(app) as client:
        response = client.put(
            "/api/dev/simulation/vehicle/speed",
            json={"speed_kph": 42.5},
        )
        snapshot = service.snapshot()

        assert response.status_code == 200
        assert snapshot.application.speed_valid is True
        assert snapshot.application.vehicle_speed_kph == 42.5
        assert client.post("/api/dev/simulation/reset").status_code == 404
        assert (
            client.post("/api/dev/simulation/devices/button-pad/buttons/0/tap").status_code == 404
        )
        assert client.post("/api/dev/simulation/devices/button-pad/disconnect").status_code == 404


def test_car_api_installs_no_simulation_routes(tmp_path: Path) -> None:
    service = build_controller_service(
        DeploymentProfile.CAR,
        config=slow_config(),
        socketcan_factory=FakeSocketCanBus,
    )
    app = create_app(
        controller_service=service,
        profile_database_path=tmp_path / "car.sqlite3",
    )

    with TestClient(app) as client:
        assert (
            client.put(
                "/api/dev/simulation/vehicle/speed",
                json={"speed_kph": 42.5},
            ).status_code
            == 404
        )


def test_car_profile_does_not_decode_synthetic_vehicle_frames() -> None:
    service = build_controller_service(
        DeploymentProfile.CAR,
        config=slow_config(),
        socketcan_factory=FakeSocketCanBus,
    )

    service.start()
    try:
        service.submit(
            ReceivedCanFrame(
                CanNetwork.FCAN,
                encode_simulated_speed(42.5),
                1.0,
            )
        ).result(timeout=0.2)
        snapshot = service.snapshot()
    finally:
        service.stop()

    assert snapshot.application.speed_valid is False
