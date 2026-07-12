"""Minimal dry-run CLI."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from e87canbus.config import default_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="E87 CAN bus control scaffold")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print configuration without opening CAN",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = default_config()
    if not args.dry_run:
        print("Live CAN startup is not implemented yet. Re-run with --dry-run.")
        return 2

    print(json.dumps(asdict(config), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
