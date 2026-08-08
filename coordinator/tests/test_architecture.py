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


def called_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


# Domain-layer import direction (application/features must not import kernel,
# service, adapters, protocol, api, ...) is enforced declaratively by the
# import-linter contracts in pyproject.toml (`uv run lint-imports`). The tests
# below cover the project-specific safety invariants import-linter cannot express.


def test_wire_codecs_do_not_import_application_types() -> None:
    for name in ("can.py", "generated.py"):
        path = PACKAGE / "protocol" / name
        assert not any(
            module == "e87canbus.domain" or module.startswith("e87canbus.domain.")
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


def test_default_live_composition_has_no_transmit_grant() -> None:
    assert not any(network.tx_enabled for network in default_config().can_networks)


def test_simulation_protocol_and_devices_stay_inside_simulation_composition() -> None:
    simulation_composition_imports = {
        PACKAGE / "runners" / "composition.py": {
            "e87canbus.runners.simulation.devices",
            "e87canbus.runners.simulation.runtime",
            "e87canbus.runners.simulation.vehicle_source",
        },
        PACKAGE / "deployment.py": set(),
        PACKAGE / "runners" / "live.py": {
            "e87canbus.runners.simulation.commands",
            "e87canbus.runners.simulation.protocol",
            "e87canbus.runners.simulation.vehicle_source",
        },
        PACKAGE / "api" / "main.py": {"e87canbus.runners.simulation.api"},
    }
    for path in PACKAGE.rglob("*.py"):
        if "simulation" in path.relative_to(PACKAGE).parts:
            continue
        simulation_imports = {
            module
            for module in imported_modules(path)
            if module == "e87canbus.runners.simulation"
            or module.startswith("e87canbus.runners.simulation.")
        }
        assert simulation_imports == simulation_composition_imports.get(path, set()), (
            f"{path.relative_to(PACKAGE)} has unexpected simulation imports"
        )


def test_live_composition_supplies_no_steering_actuator() -> None:
    assert "steering_actuator=" not in (PACKAGE / "runners" / "live.py").read_text()


def test_closed_event_effect_failure_and_input_boundaries_are_exhaustive() -> None:
    paths = (
        PACKAGE / "domain" / "controller" / "reducer.py",
        PACKAGE / "domain" / "controller" / "intents.py",
        PACKAGE / "adapters" / "output.py",
        PACKAGE / "kernel" / "kernel.py",
        PACKAGE / "runners" / "live.py",
        PACKAGE / "runners" / "simulation" / "effect_failures.py",
    )

    assert all("assert_never" in called_names(path) for path in paths)
