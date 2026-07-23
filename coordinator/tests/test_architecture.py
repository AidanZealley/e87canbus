import ast
from collections.abc import Iterable
from pathlib import Path

from e87canbus.config import default_config

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "e87canbus"


def python_files(*directories: str) -> Iterable[Path]:
    for directory in directories:
        yield from (PACKAGE / directory).rglob("*.py")


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def called_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_domain_and_application_import_inwards_only() -> None:
    forbidden = {
        "e87canbus.protocol",
        "e87canbus.kernel",
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
    forbidden = {
        "ButtonPressed",
        "SpeedObserved",
        "EngineRpmObserved",
        "OilTemperatureObserved",
        "CoolantTemperatureObserved",
        "ControlTimerElapsed",
        "SteeringFallbackRequested",
    }
    for path in (
        PACKAGE / "simulation" / "commands.py",
        PACKAGE / "simulation" / "runtime.py",
    ):
        tree = ast.parse(path.read_text(), filename=str(path))
        constructed = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert constructed.isdisjoint(forbidden)


def test_default_live_composition_has_no_transmit_grant() -> None:
    assert not any(network.tx_enabled for network in default_config().can_networks)


def test_simulation_protocol_and_devices_stay_inside_simulation_composition() -> None:
    simulation_composition_imports = {
        PACKAGE / "composition.py": {
            "e87canbus.simulation.devices",
            "e87canbus.simulation.runtime",
            "e87canbus.simulation.vehicle_source",
        },
        PACKAGE / "deployment.py": set(),
        PACKAGE / "live.py": {
            "e87canbus.simulation.commands",
            "e87canbus.simulation.protocol",
            "e87canbus.simulation.vehicle_source",
        },
        PACKAGE / "api" / "main.py": {"e87canbus.simulation.api"},
    }
    for path in PACKAGE.rglob("*.py"):
        if "simulation" in path.relative_to(PACKAGE).parts:
            continue
        simulation_imports = {
            module
            for module in imported_modules(path)
            if module == "e87canbus.simulation" or module.startswith("e87canbus.simulation.")
        }
        assert simulation_imports == simulation_composition_imports.get(path, set()), (
            f"{path.relative_to(PACKAGE)} has unexpected simulation imports"
        )


def test_live_composition_supplies_no_steering_actuator() -> None:
    assert "steering_actuator=" not in (PACKAGE / "live.py").read_text()


def test_closed_event_effect_failure_and_input_boundaries_are_exhaustive() -> None:
    paths = (
        PACKAGE / "application" / "controller" / "reducer.py",
        PACKAGE / "application" / "controller" / "intents.py",
        PACKAGE / "adapters" / "output.py",
        PACKAGE / "kernel" / "kernel.py",
        PACKAGE / "live.py",
        PACKAGE / "simulation" / "runtime.py",
    )

    assert all("assert_never" in called_names(path) for path in paths)
