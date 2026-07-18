from __future__ import annotations

from pathlib import Path
from typing import Any

from e87canbus.api.main import create_app
from e87canbus.deployment import DeploymentProfile


def schema_for(profile: DeploymentProfile, database_path: Path) -> dict[str, Any]:
    return create_app(profile=profile, profile_database_path=database_path).openapi()


def operations(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        operation
        for path_item in schema["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "delete"}
    ]


def test_simulator_schema_has_stable_unique_operation_ids(tmp_path: Path) -> None:
    schema = schema_for(DeploymentProfile.SIMULATOR, tmp_path / "simulator.sqlite3")
    operation_ids = [operation["operationId"] for operation in operations(schema)]

    assert len(operation_ids) == 28
    assert len(operation_ids) == len(set(operation_ids))
    assert "getApplicationSettings" in operation_ids
    assert "resetSimulation" in operation_ids


def test_schema_models_actual_success_and_problem_responses(tmp_path: Path) -> None:
    schema = schema_for(DeploymentProfile.SIMULATOR, tmp_path / "simulator.sqlite3")
    settings_update = schema["paths"]["/api/settings"]["put"]
    profiles = schema["paths"]["/api/steering/profiles"]["get"]
    readiness = schema["paths"]["/health/ready"]["get"]

    assert settings_update["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ApplicationSettingsResponse"
    }
    assert settings_update["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ApiProblemResponse"
    }
    assert profiles["responses"]["200"]["content"]["application/json"]["schema"] == {
        "items": {"$ref": "#/components/schemas/SteeringProfileResponse"},
        "title": "Response Liststeeringprofiles",
        "type": "array",
    }
    assert readiness["responses"]["503"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ReadinessResponse"
    }

    validation_issue = schema["components"]["schemas"]["ValidationIssue"]
    assert validation_issue["properties"]["location"]["items"]["anyOf"] == [
        {"type": "string"},
        {"type": "integer"},
    ]


def test_profile_schemas_preserve_runtime_route_scopes(tmp_path: Path) -> None:
    car_paths = schema_for(DeploymentProfile.CAR, tmp_path / "car.sqlite3")["paths"]
    bench_paths = schema_for(DeploymentProfile.BENCH, tmp_path / "bench.sqlite3")["paths"]
    simulator_paths = schema_for(
        DeploymentProfile.SIMULATOR, tmp_path / "simulator.sqlite3"
    )["paths"]

    vehicle_path = "/api/dev/simulation/vehicle/speed"
    device_path = "/api/dev/simulation/devices/{role}/connect"
    reset_path = "/api/dev/simulation/reset"
    assert vehicle_path not in car_paths
    assert vehicle_path in bench_paths
    assert device_path not in bench_paths
    assert reset_path not in bench_paths
    assert {vehicle_path, device_path, reset_path}.issubset(simulator_paths)
