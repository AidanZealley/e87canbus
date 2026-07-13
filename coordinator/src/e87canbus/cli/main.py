"""Coordinator command-line entry point."""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Sequence
from dataclasses import asdict

from e87canbus import live
from e87canbus.config import default_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="E87 CAN bus control scaffold")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print configuration without opening CAN",
    )
    parser.add_argument("--log-level", default="INFO")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = default_config()
    if not args.dry_run:
        return live.run_live(config)

    print(json.dumps(asdict(config), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
