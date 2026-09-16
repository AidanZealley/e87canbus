"""Workstation defaults read from the repository `.env` and the process environment.

Each supported variable stands in for a command-line flag, so options resolve as
flag, then environment, then the interactive prompt. `load_environment` runs once
at CLI startup; nothing below the CLI reads the environment directly.

A real environment variable always wins over a value in `.env`, so a one-off
`E87CTL_PROFILE=bench uv run e87ctl ...` still works.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_environment() -> None:
    load_dotenv(repository_root() / ".env", override=False)


def environment_value(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def environment_path(name: str) -> Path | None:
    value = environment_value(name)
    return Path(value).expanduser() if value else None
