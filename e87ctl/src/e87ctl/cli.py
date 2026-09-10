from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from e87ctl.recovery import (
    InstallationSummary,
    create_recovery_package,
    write_recovery_package,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="e87ctl")
    commands = parser.add_subparsers(dest="command", required=True)

    image = commands.add_parser("image", help="Manage Raspberry Pi host images")
    image_commands = image.add_subparsers(dest="image_command", required=True)

    build = image_commands.add_parser("build", help="Build a Raspberry Pi host image")
    build.add_argument("role", choices=("coordinator", "console"))

    installation = commands.add_parser("installation", help="Manage an installation")
    installation_commands = installation.add_subparsers(dest="installation_command", required=True)
    create = installation_commands.add_parser(
        "create", help="Create an installation recovery package"
    )
    create.add_argument("--output", required=True, type=Path, metavar="PATH")
    create.add_argument("--json", action="store_true", help="Print a machine-readable summary")
    return parser


def _build_image(role: str) -> int:
    script = Path(__file__).resolve().parents[2] / "scripts" / "build-pi-image"
    return subprocess.run([script, role], check=False).returncode


def _create_installation(output: Path, json_output: bool) -> int:
    # Nothing below this boundary may expose an exception carrying generated material.
    try:
        package = create_recovery_package()
        sidecar = write_recovery_package(output, package)
    except Exception:
        print("error: could not create installation", file=sys.stderr)
        return 1

    summary = InstallationSummary(
        installation_id=package.installation_id,
        recovery_package=str(output),
        ca_certificate=str(sidecar),
    )
    if json_output:
        print(json.dumps(summary.model_dump(), separators=(",", ":")))
    else:
        print(f"Created installation {summary.installation_id}")
        print(f"Recovery package: {summary.recovery_package}")
        print(f"Public CA certificate: {summary.ca_certificate}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "image":
        role = getattr(arguments, "role", None)
        if not isinstance(role, str):
            raise AssertionError("image build role was not parsed")
        return _build_image(role)
    if arguments.command == "installation":
        output = getattr(arguments, "output", None)
        json_output = getattr(arguments, "json", None)
        if not isinstance(output, Path) or not isinstance(json_output, bool):
            raise AssertionError("installation create arguments were not parsed")
        return _create_installation(output, json_output)
    raise AssertionError("command was not parsed")
