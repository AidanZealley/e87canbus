from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from e87canbus.console.models import ConsoleSnapshot

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = ROOT / "scripts" / "generate_console_live_contract.py"
SCHEMA = ROOT / "protocol" / "console-live-v1.schema.json"
OPENAPI_GENERATOR = ROOT / "scripts" / "generate_console_openapi.py"
OPENAPI = ROOT / "protocol" / "console-openapi.json"


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_console_live_contract", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_console_contract_schema_matches_python_model_and_committed_artifact() -> None:
    generator = load_generator()
    schema = json.loads(SCHEMA.read_text())
    snapshot = schema["definitions"]["ConsoleSnapshot"]

    assert SCHEMA.read_text() == generator.rendered_schema()
    assert snapshot["required"] == sorted(ConsoleSnapshot.model_fields)
    assert schema["properties"]["protocol_version"]["const"] == 1
    assert (
        schema["properties"]["server_to_client_event"]["properties"]["event"]["const"]
        == "console.snapshot"
    )


def test_console_openapi_describes_the_sse_event_and_matches_committed_artifact() -> None:
    generator = load_generator_from(OPENAPI_GENERATOR, "generate_console_openapi")
    schema = json.loads(OPENAPI.read_text())
    response = schema["paths"]["/api/live"]["get"]["responses"]["200"]

    assert OPENAPI.read_text() == generator.rendered_schema()
    assert set(response["content"]) == {"text/event-stream"}
    assert response["content"]["text/event-stream"]["schema"] == {
        "$ref": "#/components/schemas/ConsoleSnapshotEvent"
    }
    event = schema["components"]["schemas"]["ConsoleSnapshotEvent"]
    assert event["properties"]["type"]["const"] == "console.snapshot"


def load_generator_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
