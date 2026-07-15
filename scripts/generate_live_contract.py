#!/usr/bin/env python3
"""Generate/check the Pydantic-owned Socket.IO version 1 contract schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from e87canbus.api.models.live import LiveEnvelope
from e87canbus.api.models.resources import ResourceChangedEvent

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "protocol" / "live-events-v1.schema.json"
SERVER_EVENTS = (
    "controller.snapshot",
    "vehicle.state",
    "engine.state",
    "steering.state",
    "buttons.state",
    "devices.state",
    "controller.health",
    "resources.changed",
    "trace.batch",
)
CLIENT_EVENTS = (
    "controller.resync",
    "trace.subscribe",
    "trace.unsubscribe",
)


def rendered_schema() -> str:
    document = {
        "protocol_version": 1,
        "server_events": SERVER_EVENTS,
        "client_transport_events": CLIENT_EVENTS,
        "live_envelope": LiveEnvelope.model_json_schema(),
        "resource_changed": ResourceChangedEvent.model_json_schema(),
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


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
