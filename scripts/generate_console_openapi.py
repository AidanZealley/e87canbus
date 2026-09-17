#!/usr/bin/env python3
"""Generate/check the console host's OpenAPI document."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from e87canbus.console.app import create_app

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "protocol" / "console-openapi.json"


def rendered_schema() -> str:
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = rendered_schema()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != expected:
            print(f"generated console OpenAPI contract is stale: {OUTPUT}")
            return 1
        return 0
    OUTPUT.write_text(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
