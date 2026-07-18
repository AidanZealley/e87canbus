"""Canonical unified-controller command-line entry point."""

from __future__ import annotations

import argparse
import json
import logging
import os
import threading
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path

import uvicorn

from e87canbus.api import main as api_main
from e87canbus.api.main import (
    DEFAULT_PROFILE_DATABASE,
    DEPLOYMENT_PROFILE_ENVIRONMENT_VARIABLE,
    PROFILE_DATABASE_ENVIRONMENT_VARIABLE,
    create_app,
)
from e87canbus.composition import build_controller_service
from e87canbus.deployment import CanTransport, DeploymentProfile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the unified E87 controller and API")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("run",),
        default="run",
        help="Controller operation (defaults to run).",
    )
    parser.add_argument(
        "--profile",
        choices=tuple(DeploymentProfile),
        default=os.environ.get(
            DEPLOYMENT_PROFILE_ENVIRONMENT_VARIABLE,
            DeploymentProfile.CAR,
        ),
        help="Named deployment composition (car, bench, or simulator).",
    )
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
        "--frontend-directory",
        type=Path,
        help="Built frontend directory served same-origin by the controller.",
    )
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
    selected_profile = DeploymentProfile(args.profile)
    service = build_controller_service(
        selected_profile,
        profile_database_path=args.profile_database,
    )
    if (
        service.deployment.transport is CanTransport.SOCKETCAN
        and args.host not in {"127.0.0.1", "::1", "localhost"}
    ):
        raise ValueError(
            "SocketCAN profiles are unauthenticated and may bind only to loopback; "
            "non-loopback exposure requires a separate security decision"
        )
    if args.dry_run:
        dry_run_output: dict[str, object] = {
            "profile": selected_profile.value,
            "transport": service.deployment.transport.value,
            "config": asdict(service.config),
            "device_adapters": [
                {"role": role.value, "source": source.value}
                for role, source in service.deployment.device_sources
            ],
            "simulation_api": service.deployment.simulation_api.value,
        }
        print(json.dumps(dry_run_output, indent=2, sort_keys=True))
        return 0

    os.environ[PROFILE_DATABASE_ENVIRONMENT_VARIABLE] = str(args.profile_database)
    os.environ[DEPLOYMENT_PROFILE_ENVIRONMENT_VARIABLE] = selected_profile.value
    api_main.app = create_app(
        controller_service=service,
        profile_database_path=args.profile_database,
        cors_origins=args.cors_origins,
        frontend_directory=args.frontend_directory,
    )
    if args.reload:
        uvicorn.run(
            "e87canbus.api.main:app",
            host=args.host,
            port=args.port,
            log_level=args.log_level,
            reload=True,
            reload_dirs=["coordinator/src"],
        )
        return 0

    server = uvicorn.Server(
        uvicorn.Config(
            "e87canbus.api.main:app",
            host=args.host,
            port=args.port,
            log_level=args.log_level,
        )
    )
    monitor_cancel = threading.Event()

    def monitor_controller() -> None:
        while (
            not monitor_cancel.wait(0.05)
            and not api_main.app.state.controller_service.stopped_event.is_set()
        ):
            pass
        if api_main.app.state.controller_service.fatal_exit_required:
            server.should_exit = True

    monitor = threading.Thread(
        target=monitor_controller,
        name="controller-fatal-monitor",
    )
    monitor.start()
    try:
        with suppress(KeyboardInterrupt):
            server.run()
    finally:
        monitor_cancel.set()
        monitor.join(timeout=1.0)
        if monitor.is_alive():
            raise RuntimeError("controller fatal monitor did not stop cleanly")
    return 1 if (
        not server.started
        or api_main.app.state.controller_service.fatal_exit_required
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
