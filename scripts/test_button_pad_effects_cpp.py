#!/usr/bin/env python3
"""Compile and run the pure C++ renderer against the shared protocol vectors."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "protocol/test-vectors/button-pad-program-v2.json"
LIBRARY = ROOT / "embedded-libs/button_pad_effects"


def byte_initializer(hex_value: str) -> str:
    return ", ".join(f"0x{byte:02x}" for byte in bytes.fromhex(hex_value))


def generated_header(data: dict[str, Any]) -> str:
    lines = [
        "#pragma once",
        "#include <array>",
        "#include <stdint.h>",
        "#include <vector>",
        "struct FrameVector { uint32_t elapsed_ms; uint16_t animation_mask; "
        "std::array<uint8_t, 48> rgb; };",
        "struct ProgramVector { const char *name; std::vector<std::vector<uint8_t>> commands; "
        "std::vector<FrameVector> frames; };",
        "struct InvalidProgramVector { const char *name; std::vector<uint8_t> payload; };",
        "static const std::vector<ProgramVector> VALID_PROGRAMS = {",
    ]
    for program in data["programs"]:
        commands = ", ".join(
            "{" + byte_initializer(value) + "}" for value in program["commands_hex"]
        )
        frames = ", ".join(
            "{"
            + str(frame["elapsed_ms"])
            + ", "
            + str(frame["animation_mask"])
            + ", {"
            + byte_initializer(frame["rgb_hex"])
            + "}}"
            for frame in program["frames"]
        )
        lines.append('{"' + program["name"] + '", {' + commands + "}" + ", {" + frames + "}},")
    lines.append("};")
    lines.append("static const std::vector<InvalidProgramVector> INVALID_PROGRAMS = {")
    for program in data["invalid_commands"]:
        lines.append(
            '{"' + program["name"] + '", {' + byte_initializer(program["payload_hex"]) + "}},"
        )
    lines.extend(("};", ""))
    return "\n".join(lines)


def main() -> int:
    compiler = os.environ.get("CXX") or shutil.which("c++")
    if compiler is None:
        print("no C++ compiler found", file=sys.stderr)
        return 2
    data = json.loads(VECTORS.read_text())
    with tempfile.TemporaryDirectory(prefix="button-pad-effects-") as temporary:
        build = Path(temporary)
        (build / "button_pad_vectors.generated.h").write_text(generated_header(data))
        executable = build / "button_pad_effects_test"
        subprocess.run(
            [
                compiler,
                "-std=c++17",
                "-Wall",
                "-Wextra",
                "-Werror",
                f"-I{LIBRARY / 'src'}",
                f"-I{build}",
                str(LIBRARY / "src/button_pad_effects.cpp"),
                str(LIBRARY / "tests/button_pad_effects_test.cpp"),
                "-o",
                str(executable),
            ],
            check=True,
        )
        subprocess.run([str(executable)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
