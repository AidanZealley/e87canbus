from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from e87ctl.macos import SystemDiskutil
from e87ctl.provision import (
    ProvisionCommandError,
    choose_disk,
    choose_image,
    choose_profile,
    confirmation_value,
    describe_disk,
    provision_card,
)
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

    provision = commands.add_parser("provision", help="Prepare a Raspberry Pi SD card")
    provision.add_argument("role", choices=("coordinator", "console"))
    provision.add_argument("--installation", required=True, type=Path, metavar="PATH")
    provision.add_argument("--image", type=Path, metavar="MANIFEST")
    provision.add_argument("--disk", metavar="DISK")
    provision.add_argument("--profile", choices=("car", "bench"))
    provision.add_argument("--hostname")
    provision.add_argument(
        "--confirm", metavar="TEXT", help="Supply the exact confirmation text for the disk"
    )
    provision.add_argument("--non-interactive", action="store_true")
    provision.add_argument("--json", action="store_true", help="Print a machine-readable result")
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


def _provision(arguments: argparse.Namespace) -> int:
    if sys.platform != "darwin":
        print("error: provisioning is supported only on macOS", file=sys.stderr)
        return 1
    if arguments.json and not arguments.non_interactive:
        print("error: --json requires --non-interactive", file=sys.stderr)
        return 1
    if arguments.non_interactive:
        missing = [
            option
            for option, value in (
                ("--image", arguments.image),
                ("--disk", arguments.disk),
                ("--profile", arguments.profile),
                ("--confirm", arguments.confirm),
            )
            if value is None
        ]
        if missing:
            print(
                f"error: --non-interactive requires {', '.join(missing)}",
                file=sys.stderr,
            )
            return 1

    repository = Path(__file__).resolve().parents[3]
    diskutil = SystemDiskutil()
    try:
        image = choose_image(
            repository, arguments.role, str(arguments.image) if arguments.image else None
        )
        target = choose_disk(diskutil, arguments.disk)
        profile = choose_profile(arguments.profile)
        confirmation = arguments.confirm
        if confirmation is None:
            print("Destructive action:")
            print(f"  Role: {arguments.role}")
            print(f"  Image manifest: {image}")
            print(f"  Profile: {profile}")
            print(f"  Target: {describe_disk(target)}")
            expected_confirmation = confirmation_value(target)
            confirmation = input(
                f"Type '{expected_confirmation}' to erase and provision this disk: "
            )
        result = provision_card(
            arguments.role,
            installation_path=arguments.installation,
            image_manifest_path=image,
            expected_target=target,
            deployment_profile=profile,
            confirmation=confirmation,
            hostname=arguments.hostname,
            repository=repository,
            diskutil=diskutil,
        )
    except (ProvisionCommandError, EOFError) as error:
        message = (
            str(error)
            if isinstance(error, ProvisionCommandError)
            else "confirmation was not provided"
        )
        print(f"error: {message}", file=sys.stderr)
        return 1

    if arguments.json:
        print(json.dumps(result.model_dump(), separators=(",", ":")))
    else:
        print(f"Prepared {result.role} {result.hostname}")
        serial = result.target_serial or "not reported"
        mounts = ", ".join(result.target_mounts) or "none"
        print(
            f"Target: {result.target_device}: {result.target_model}, "
            f"{result.target_capacity_bytes} bytes, serial {serial}, "
            f"{result.target_protocol}, mounts {mounts}"
        )
        print(f"Device ID: {result.device_id}")
        print(f"Installation ID: {result.installation_id}")
        print(f"Image SHA-256: {result.image_digest}")
        print(f"Application SHA-256: {result.application_digest}")
        print(f"Provisioning SHA-256: {result.provisioning_digest}")
        print("First boot: pending")
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
    if arguments.command == "provision":
        return _provision(arguments)
    raise AssertionError("command was not parsed")
