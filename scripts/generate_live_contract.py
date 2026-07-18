#!/usr/bin/env python3
"""Generate/check the backend-owned Socket.IO version 1 JSON Schema."""

from __future__ import annotations

import argparse
import json
import re
from functools import reduce
from operator import or_
from pathlib import Path
from typing import Any, Literal

from e87canbus.api.models.live import PROTOCOL_VERSION, LiveEnvelope, LiveModel
from e87canbus.api.models.live_contract import (
    CLIENT_EVENT_CONTRACTS,
    SERVER_EVENT_CONTRACTS,
    EventContract,
)
from pydantic import BaseModel, TypeAdapter, create_model

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "protocol" / f"live-events-v{PROTOCOL_VERSION}.schema.json"


def _model_name(contract: EventContract) -> str:
    words = re.split(r"[._-]", str(contract.name))
    return "".join(word.title() for word in words) + "Event"


def _event_model(contract: EventContract) -> type[BaseModel]:
    event_type = Literal[contract.name.value]  # type: ignore[valid-type]
    if contract.payload is None:
        args_type: Any = tuple[()]
    else:
        payload_type = (
            LiveEnvelope[contract.payload] if contract.enveloped else contract.payload
        )
        args_type = tuple[payload_type]
    return create_model(
        _model_name(contract),
        __base__=LiveModel,
        event=(event_type, ...),
        args=(args_type, ...),
    )


def _union_schema(contracts: tuple[EventContract, ...]) -> dict[str, Any]:
    models = tuple(_event_model(contract) for contract in contracts)
    union = reduce(or_, models)
    schema = TypeAdapter(union).json_schema(
        mode="serialization",
        ref_template="#/definitions/{model}",
    )
    _require_serialized_defaults(schema)
    _use_draft_7_tuples(schema)
    schema["definitions"] = schema.pop("$defs")
    return schema


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
    """Pydantic emits 2020-12 tuple keywords; use the draft-07 equivalent."""

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


def contract_schema() -> dict[str, Any]:
    server = _union_schema(SERVER_EVENT_CONTRACTS)
    client = _union_schema(CLIENT_EVENT_CONTRACTS)
    definitions = server.pop("definitions") | client.pop("definitions")
    definitions["ServerToClientEvent"] = server
    definitions["ClientToServerEvent"] = client
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": f"https://e87canbus.local/protocol/live-events-v{PROTOCOL_VERSION}.schema.json",
        "title": "LiveSocketContract",
        "description": (
            "Generated Socket.IO protocol contract. The protocol version is encoded "
            "in each server payload envelope and in this document's identifier."
        ),
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "protocol_version": {"const": PROTOCOL_VERSION, "type": "integer"},
            "server_to_client_event": {"$ref": "#/definitions/ServerToClientEvent"},
            "client_to_server_event": {"$ref": "#/definitions/ClientToServerEvent"},
        },
        "required": [
            "protocol_version",
            "server_to_client_event",
            "client_to_server_event",
        ],
        "definitions": definitions,
    }


def rendered_schema() -> str:
    return json.dumps(contract_schema(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = rendered_schema()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != expected:
            print(f"generated live contract is stale: {OUTPUT}")
            return 1
        return 0
    OUTPUT.write_text(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
