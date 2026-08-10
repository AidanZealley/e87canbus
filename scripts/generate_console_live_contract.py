#!/usr/bin/env python3
"""Generate/check the console's backend-owned Socket.IO version 1 JSON Schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from e87canbus.console.models import (
    CONSOLE_PROTOCOL_VERSION,
    CONSOLE_SNAPSHOT_EVENT,
    ConsoleLiveModel,
    ConsoleSnapshot,
)
from pydantic import TypeAdapter, create_model

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "protocol" / "console-live-v1.schema.json"


def contract_schema() -> dict[str, object]:
    event_type = Literal[CONSOLE_SNAPSHOT_EVENT]  # type: ignore[valid-type]
    event_model = create_model(
        "ConsoleSnapshotEvent",
        __base__=ConsoleLiveModel,
        event=(event_type, ...),
        args=(tuple[ConsoleSnapshot], ...),
    )
    event_schema = TypeAdapter(event_model).json_schema(
        mode="serialization",
        ref_template="#/definitions/{model}",
    )
    _require_serialized_defaults(event_schema)
    _use_draft_7_tuples(event_schema)
    definitions = event_schema.pop("$defs")
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "https://e87canbus.local/protocol/console-live-v1.schema.json",
        "title": "ConsoleLiveSocketContract",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "protocol_version": {
                "const": CONSOLE_PROTOCOL_VERSION,
                "type": "integer",
            },
            "server_to_client_event": event_schema,
        },
        "required": ["protocol_version", "server_to_client_event"],
        "definitions": definitions,
    }


def _require_serialized_defaults(value: object) -> None:
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            required = set(value.get("required", ()))
            required.update(
                name
                for name, schema in properties.items()
                if isinstance(schema, dict) and "default" in schema
            )
            if required:
                value["required"] = sorted(required)
        for child in value.values():
            _require_serialized_defaults(child)
    elif isinstance(value, list):
        for child in value:
            _require_serialized_defaults(child)


def _use_draft_7_tuples(value: object) -> None:
    if isinstance(value, dict):
        prefix_items = value.pop("prefixItems", None)
        if prefix_items is not None:
            value["items"] = prefix_items
            value["additionalItems"] = False
        for child in value.values():
            _use_draft_7_tuples(child)
    elif isinstance(value, list):
        for child in value:
            _use_draft_7_tuples(child)


def rendered_schema() -> str:
    return json.dumps(contract_schema(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = rendered_schema()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != expected:
            print(f"generated console live contract is stale: {OUTPUT}")
            return 1
        return 0
    OUTPUT.write_text(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
