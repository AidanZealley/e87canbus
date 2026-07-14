"""Command-line entry point for the workbench API."""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Sequence
from pathlib import Path

import uvicorn

from e87canbus.api import main as api_main
from e87canbus.api.main import (
    DEFAULT_PROFILE_DATABASE,
    PROFILE_DATABASE_ENVIRONMENT_VARIABLE,
    create_app,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the E87 CAN workbench API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log-level", default="info")
    parser.add_argument(
        "--profile-database",
        type=Path,
        default=DEFAULT_PROFILE_DATABASE,
        help="SQLite steering-profile database path.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Restart the development server when Python source files change.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    os.environ[PROFILE_DATABASE_ENVIRONMENT_VARIABLE] = str(args.profile_database)
    api_main.app = create_app(profile_database_path=args.profile_database)
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
