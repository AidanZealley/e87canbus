import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "generate_live_contract", ROOT / "scripts" / "generate_live_contract.py"
)
assert SPEC is not None and SPEC.loader is not None
GENERATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GENERATOR
SPEC.loader.exec_module(GENERATOR)


def test_generated_live_contract_is_current() -> None:
    assert GENERATOR.OUTPUT.read_text() == GENERATOR.rendered_schema()


def test_typescript_map_names_every_fixed_transport_event() -> None:
    typescript = (ROOT / "frontend" / "src" / "api" / "live-events.ts").read_text()

    for event in (*GENERATOR.SERVER_EVENTS, *GENERATOR.CLIENT_EVENTS):
        assert f'"{event}"' in typescript
