"""Canonical unified-controller command-line entry point."""

from __future__ import annotations

import argparse
import json
import logging
import os
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

import uvicorn

from e87canbus.api import main as api_main
from e87canbus.api.main import (
    CONTROLLER_MODE_ENVIRONMENT_VARIABLE,
    DEFAULT_CORS_ORIGINS,
    DEFAULT_PROFILE_DATABASE,
    PROFILE_DATABASE_ENVIRONMENT_VARIABLE,
    create_app,
)
from e87canbus.config import default_config, simulator_config
from e87canbus.service import ControllerMode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the unified E87 controller and API")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("run",),
        default="run",
        help="Controller operation (defaults to run for live-runner compatibility).",
    )
    parser.add_argument("--mode", choices=tuple(ControllerMode), default=ControllerMode.LIVE)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log-level", default="info")
    parser.add_argument(
        "--cors-origin",
        action="append",
        dest="cors_origins",
        help="Allowed browser origin; repeat for multiple origins.",
    )
    parser.add_argument(
        "--profile-database",
        type=Path,
        default=DEFAULT_PROFILE_DATABASE,
        help="Shared SQLite application database path.",
    )
    parser.add_argument("--reload", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the selected configuration without opening adapters.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    mode = ControllerMode(args.mode)
    config = simulator_config() if mode is ControllerMode.SIMULATED else default_config()
    if args.dry_run:
        print(
            json.dumps(
                {"mode": mode.value, "config": asdict(config)},
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    os.environ[PROFILE_DATABASE_ENVIRONMENT_VARIABLE] = str(args.profile_database)
    os.environ[CONTROLLER_MODE_ENVIRONMENT_VARIABLE] = mode.value
    api_main.app = create_app(
        mode=mode,
        config=config,
        profile_database_path=args.profile_database,
        cors_origins=args.cors_origins or DEFAULT_CORS_ORIGINS,
    )
    uvicorn.run(
        "e87canbus.api.main:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
        reload_dirs=["coordinator/src"] if args.reload else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
