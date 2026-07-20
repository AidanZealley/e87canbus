from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_native_button_pad_renderer_matches_shared_vectors() -> None:
    if shutil.which("c++") is None:
        pytest.skip("a native C++ compiler is unavailable")
    root = Path(__file__).parents[2]
    subprocess.run(
        [sys.executable, str(root / "scripts/test_button_pad_effects_cpp.py")],
        cwd=root,
        check=True,
    )
