import importlib.util
import sys
from pathlib import Path

from e87canbus.api.internal.live import TOPIC_EVENTS
from e87canbus.api.models.live import STEERING_CURVE_POINT_COUNT, VehicleState
from e87canbus.api.models.live_contract import (
    CLIENT_EVENT_CONTRACTS,
    EVENT_CONTRACTS,
    SERVER_EVENT_CONTRACTS,
    ClientEvent,
    ServerEvent,
)

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "generate_live_contract", ROOT / "scripts" / "generate_live_contract.py"
)
assert SPEC is not None and SPEC.loader is not None
GENERATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GENERATOR
SPEC.loader.exec_module(GENERATOR)


def test_generated_live_contract_is_current() -> None:
    assert GENERATOR.OUTPUT.read_text() == GENERATOR.rendered_schema()


def test_contract_registry_owns_every_unique_transport_event() -> None:
    names = [contract.name for contract in EVENT_CONTRACTS]
    assert len(names) == len(set(names))
    assert {contract.name for contract in SERVER_EVENT_CONTRACTS} == set(ServerEvent)
    assert {contract.name for contract in CLIENT_EVENT_CONTRACTS} == set(ClientEvent)
    assert all(contract.payload is not None for contract in SERVER_EVENT_CONTRACTS)
    assert all(contract.payload is None for contract in CLIENT_EVENT_CONTRACTS)


def test_runtime_topic_names_are_contract_owned() -> None:
    assert set(TOPIC_EVENTS.values()) == {
        ServerEvent.VEHICLE_STATE,
        ServerEvent.ENGINE_STATE,
        ServerEvent.STEERING_STATE,
        ServerEvent.BUTTONS_STATE,
        ServerEvent.LIGHTING_STATE,
        ServerEvent.DEVICES_STATE,
        ServerEvent.CONTROLLER_HEALTH,
    }


def test_vehicle_event_schema_has_its_exact_enveloped_payload() -> None:
    schema = GENERATOR.contract_schema()
    definitions = schema["definitions"]
    vehicle_event = definitions["VehicleStateEvent"]
    envelope_ref = vehicle_event["properties"]["args"]["items"][0]["$ref"]
    envelope = definitions[envelope_ref.rsplit("/", 1)[1]]

    assert envelope["properties"]["data"]["$ref"] == "#/definitions/VehicleState"
    vehicle_contract = next(
        contract
        for contract in SERVER_EVENT_CONTRACTS
        if contract.name is ServerEvent.VEHICLE_STATE
    )
    assert vehicle_contract.payload is VehicleState


def test_live_steering_curve_schema_requires_the_domain_point_count() -> None:
    points = GENERATOR.contract_schema()["definitions"]["SteeringCurveDefinition"][
        "properties"
    ]["points"]

    assert points["minItems"] == STEERING_CURVE_POINT_COUNT
    assert points["maxItems"] == STEERING_CURVE_POINT_COUNT
