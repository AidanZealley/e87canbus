from __future__ import annotations

import argparse
import subprocess
from collections.abc import Sequence
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="e87ctl")
    commands = parser.add_subparsers(dest="command", required=True)

    image = commands.add_parser("image", help="Manage Raspberry Pi host images")
    image_commands = image.add_subparsers(dest="image_command", required=True)

    build = image_commands.add_parser("build", help="Build a Raspberry Pi host image")
    build.add_argument("role", choices=("coordinator", "console"))
    return parser


def _build_image(role: str) -> int:
    script = Path(__file__).resolve().parents[2] / "scripts" / "build-pi-image"
    return subprocess.run([script, role], check=False).returncode


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    role = getattr(arguments, "role", None)
    if not isinstance(role, str):
        raise AssertionError("image build role was not parsed")
    return _build_image(role)
