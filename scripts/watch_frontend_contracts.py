#!/usr/bin/env python3
"""Regenerate frontend contracts when their Python sources change."""

from __future__ import annotations

import subprocess
from pathlib import Path

from watchfiles import PythonFilter, watch

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
WATCH_PATHS = (ROOT / "coordinator" / "src" / "e87canbus", ROOT / "scripts")


def generate() -> None:
    result = subprocess.run(["pnpm", "api:generate"], cwd=FRONTEND, check=False)
    if result.returncode:
        print(
            "Contract generation failed; keeping the last valid generated output "
            "and waiting for another change.",
            flush=True,
        )


def main() -> int:
    generate()
    try:
        for _changes in watch(*WATCH_PATHS, watch_filter=PythonFilter()):
            generate()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
