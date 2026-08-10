from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from e87canbus.console.models import ConsoleSnapshot

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = ROOT / "scripts" / "generate_console_live_contract.py"
SCHEMA = ROOT / "protocol" / "console-live-v1.schema.json"


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
