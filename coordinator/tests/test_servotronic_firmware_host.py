from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_servotronic_curve_matches_shared_conformance_vectors(tmp_path: Path) -> None:
    """Compile firmware logic against every shared monotone-cubic-v1 vector."""

    vectors = json.loads(
        (ROOT / "test-fixtures/steering/monotone-cubic-v1-vectors.json").read_text()
    )
    speeds = vectors["speeds_deci_kph"]
    assertions: list[str] = []
    for case in vectors["cases"]:
        values_name = f"values_{len(assertions)}"
        values = ",".join(str(value) for value in case["assistance_per_mille"])
        assertions.append(f"const uint16_t {values_name}[] = {{{values}}};")
        for speed, expected in case["evaluations"]:
            if speed < 0:
                # Firmware accepts only non-negative vehicle speed; clamping below
                # the first knot is already covered by the zero-speed vector.
                continue
            expected_literal = f"{expected:.17g}"
            if "." not in expected_literal:
                expected_literal += ".0"
            assertions.append(
                "assert(std::fabs(servotronic::interpolateMonotoneCubicV1("
                f"{speed}, speeds, {values_name}, 8) - {expected_literal}f) <= 0.000002f);"
            )
    source = tmp_path / "servotronic_curve_test.cpp"
    source.write_text(
        "#include <cassert>\n#include <cmath>\n#include <cstdint>\n"
        '#include "servotronic_logic.h"\n'
        "int main() {\n"
        f"const uint16_t speeds[] = {{{','.join(str(speed) for speed in speeds)}}};\n"
        + "\n".join(assertions)
        + "\nreturn 0;\n}\n",
        encoding="utf-8",
    )
    compiler = shutil.which("c++")
    if compiler is None:
        pytest.skip("host C++ compiler is unavailable")
    executable = tmp_path / "servotronic_curve_test"
    subprocess.run(
        [
            compiler,
            "-std=gnu++11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(ROOT / "devices/servotronic-controller/include"),
            str(source),
            "-o",
            str(executable),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run([str(executable)], check=True)
