import ast
from collections.abc import Iterable
from pathlib import Path

from e87canbus.config import default_config

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "e87canbus"


def python_files(*directories: str) -> Iterable[Path]:
    for directory in directories:
        yield from (PACKAGE / directory).glob("*.py")


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_domain_and_application_import_inwards_only() -> None:
    forbidden = {
        "e87canbus.protocol",
        "e87canbus.runtime",
        "e87canbus.simulation",
        "e87canbus.adapters",
        "e87canbus.api",
        "fastapi",
        "threading",
        "queue",
    }

    for path in python_files("application", "features"):
        for module in imported_modules(path):
            assert not any(module == name or module.startswith(f"{name}.") for name in forbidden), (
                f"{path.relative_to(PACKAGE)} imports forbidden module {module}"
            )


def test_wire_codecs_do_not_import_application_types() -> None:
    for name in ("can.py", "generated.py"):
        path = PACKAGE / "protocol" / name
        assert not any(
            module == "e87canbus.application" or module.startswith("e87canbus.application.")
            for module in imported_modules(path)
        )


def test_simulation_commands_do_not_construct_application_events() -> None:
    path = PACKAGE / "simulation" / "engine.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    forbidden = {"ButtonPressed", "SpeedObserved", "ControlTimerElapsed"}
    constructed = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert constructed.isdisjoint(forbidden)


def test_default_live_composition_has_no_transmit_grant() -> None:
    assert not any(network.tx_enabled for network in default_config().can_networks)


def test_pre_kernel_compatibility_names_are_absent() -> None:
    obsolete = {
        "ApplicationController",
        "CoordinatorRuntime",
        "RateLimitedCanBus",
        "SimulatorController",
        "min_id_gap_s",
        "min_identical_frame_gap_s",
    }
    production = "\n".join(path.read_text() for path in PACKAGE.rglob("*.py"))

    assert not {name for name in obsolete if name in production}
