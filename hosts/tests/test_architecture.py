import ast
from pathlib import Path

from e87canbus.config import default_config

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "e87canbus"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_frame_values_do_not_import_application_types() -> None:
    assert not any(
        module == "e87canbus.domain" or module.startswith("e87canbus.domain.")
        for module in imported_modules(PACKAGE / "protocol" / "can.py")
    )


def test_simulation_commands_do_not_construct_application_events() -> None:
    forbidden = {
        "ButtonPressed",
        "SpeedObserved",
        "EngineRpmObserved",
        "OilTemperatureObserved",
        "CoolantTemperatureObserved",
        "ControlTimerElapsed",
    }
    for path in (
        PACKAGE / "runners" / "simulation" / "commands.py",
        PACKAGE / "runners" / "simulation" / "runtime.py",
    ):
        tree = ast.parse(path.read_text(), filename=str(path))
        constructed = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert constructed.isdisjoint(forbidden)


def test_live_composition_has_no_transmit_configuration() -> None:
    assert all(not hasattr(network, "tx_enabled") for network in default_config().can_networks)
    live = (PACKAGE / "runners" / "live.py").read_text()
    assert "transmitter" not in live.lower()


def test_simulation_protocol_stays_inside_simulation_composition() -> None:
    permitted = {
        PACKAGE / "runners" / "composition.py",
        PACKAGE / "runners" / "live.py",
        PACKAGE / "api" / "main.py",
    }
    for path in PACKAGE.rglob("*.py"):
        if "simulation" in path.relative_to(PACKAGE).parts or path in permitted:
            continue
        assert not any(
            module.startswith("e87canbus.runners.simulation") for module in imported_modules(path)
        )
