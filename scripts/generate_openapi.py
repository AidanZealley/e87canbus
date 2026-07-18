#!/usr/bin/env python3
"""Generate/check the canonical simulator-superset OpenAPI document."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from e87canbus.api.main import create_app
from e87canbus.deployment import DeploymentProfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "protocol" / "openapi.json"


def rendered_schema() -> str:
    with TemporaryDirectory() as temporary_directory:
        app = create_app(
            profile=DeploymentProfile.SIMULATOR,
            profile_database_path=Path(temporary_directory) / "contract.sqlite3",
        )
        schema = app.openapi()
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = rendered_schema()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != expected:
            print(f"generated OpenAPI contract is stale: {OUTPUT}")
            return 1
        return 0
    OUTPUT.write_text(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
