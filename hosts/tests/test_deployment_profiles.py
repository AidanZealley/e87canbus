from dataclasses import replace
from pathlib import Path

import pytest
from e87canbus.api.main import create_app
from e87canbus.config import CanNetwork, default_config
from e87canbus.deployment import (
    CanTransport,
    DeploymentProfile,
    SimulationApiScope,
    VehicleSource,
    deployment_spec,
)
from e87canbus.kernel import ReceivedCanFrame
from e87canbus.protocol.can import CanFrame
from e87canbus.runners.composition import (
    build_controller_loop,
    build_live_controller_loop,
    build_simulated_controller_loop,
)
from e87canbus.runners.simulation.protocol import encode_simulated_speed
from fastapi.testclient import TestClient


class FakeSocketCanBus:
    instances: list["FakeSocketCanBus"] = []

    def __init__(self, interface: str) -> None:
        self.interface = interface
        self.sent: list[CanFrame] = []
        self.instances.append(self)

    def send(self, frame: CanFrame) -> None:
        self.sent.append(frame)

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        return None

    def shutdown(self) -> None:
        pass


def slow_config():
    return replace(default_config(), tick_interval_s=60.0)


def test_closed_profiles_keep_vehicle_source_and_networks() -> None:
    car = deployment_spec(DeploymentProfile.CAR)
    bench = deployment_spec(DeploymentProfile.BENCH)
    simulator = deployment_spec(DeploymentProfile.SIMULATOR)
    assert car.transport is CanTransport.SOCKETCAN
    assert car.vehicle_source is VehicleSource.PHYSICAL
    assert car.simulation_api is SimulationApiScope.NONE
    assert bench.vehicle_source is VehicleSource.EMULATED
    assert bench.physical_networks == frozenset(CanNetwork)
    assert bench.simulation_api is SimulationApiScope.VEHICLE
    assert simulator.transport is CanTransport.IN_MEMORY
    with pytest.raises(ValueError, match="closed composition"):
        replace(car, vehicle_source=VehicleSource.EMULATED)


def test_runtime_transport_must_match_profile() -> None:
    with pytest.raises(ValueError, match="SocketCAN deployment"):
        build_live_controller_loop(deployment=deployment_spec(DeploymentProfile.SIMULATOR))
    with pytest.raises(ValueError, match="in-memory deployment"):
        build_simulated_controller_loop(deployment=deployment_spec(DeploymentProfile.CAR))


def test_bench_vehicle_api_injects_through_decoder_without_can_transmission(tmp_path: Path) -> None:
    FakeSocketCanBus.instances = []
    service = build_controller_loop(
        DeploymentProfile.BENCH, config=slow_config(), socketcan_factory=FakeSocketCanBus
    )
    app = create_app(controller_loop=service, profile_database_path=tmp_path / "bench.sqlite3")
    with TestClient(app) as client:
        response = client.put("/api/dev/simulation/vehicle/speed", json={"speed_kph": 42.5})
        snapshot = service.snapshot()
        assert response.status_code == 200
        assert snapshot.application.vehicle_speed_kph == 42.5
        assert client.post("/api/dev/simulation/reset").status_code == 404
    assert all(not bus.sent for bus in FakeSocketCanBus.instances)


def test_car_api_installs_no_simulation_routes(tmp_path: Path) -> None:
    service = build_controller_loop(
        DeploymentProfile.CAR, config=slow_config(), socketcan_factory=FakeSocketCanBus
    )
    app = create_app(controller_loop=service, profile_database_path=tmp_path / "car.sqlite3")
    with TestClient(app) as client:
        assert (
            client.put("/api/dev/simulation/vehicle/speed", json={"speed_kph": 42.5}).status_code
            == 404
        )


def test_car_ignores_synthetic_vehicle_frames() -> None:
    service = build_controller_loop(
        DeploymentProfile.CAR, config=slow_config(), socketcan_factory=FakeSocketCanBus
    )
    service.start()
    try:
        service.submit(ReceivedCanFrame(CanNetwork.FCAN, encode_simulated_speed(42.5), 1.0)).result(
            timeout=0.2
        )
        snapshot = service.snapshot()
    finally:
        service.stop()
    assert snapshot.application.vehicle_speed_kph == 0
