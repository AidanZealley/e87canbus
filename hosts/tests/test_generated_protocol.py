import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "generate_custom_protocol", ROOT / "scripts" / "generate_custom_protocol.py"
)
assert SPEC is not None and SPEC.loader is not None
GENERATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GENERATOR
SPEC.loader.exec_module(GENERATOR)

expected_artifacts = GENERATOR.expected_artifacts
load_definition = GENERATOR.load_definition
replace_markdown_section = GENERATOR.replace_markdown_section
stale_artifacts = GENERATOR.stale_artifacts


def test_generated_protocol_artifacts_are_current() -> None:
    assert stale_artifacts(ROOT) == ()


def test_definition_contains_only_servotronic_messages_and_transport() -> None:
    definition = load_definition(ROOT / "protocol" / "custom.toml")
    assert definition.protocol_version == 1
    assert {message.name for message in definition.messages} == {
        "servotronic_controller_hello",
        "servotronic_controller_welcome_ack",
        "servotronic_controller_heartbeat",
    }
    assert [message.can_id for message in definition.messages] == [0x705, 0x706, 0x707]
    assert [link.name for link in definition.transport_links] == ["servotronic_transport"]


def test_markdown_generation_preserves_surrounding_prose() -> None:
    start = "<!-- BEGIN GENERATED CUSTOM PROTOCOL -->"
    end = "<!-- END GENERATED CUSTOM PROTOCOL -->"
    document = f"before\n{start}old{end}\nafter\n"
    generated = f"{start}new{end}"

    assert replace_markdown_section(document, generated) == f"before\n{generated}\nafter\n"


@pytest.mark.parametrize(
    "relative_path",
    [
        Path("hosts/src/e87canbus/protocol/generated.py"),
        Path("devices/servotronic-controller/include/can_ids.h"),
        Path("protocol/custom_ids.md"),
    ],
)
def test_changing_one_generated_artifact_is_detected(tmp_path: Path, relative_path: Path) -> None:
    definition = load_definition(ROOT / "protocol" / "custom.toml")
    (tmp_path / "protocol").mkdir(parents=True)
    (tmp_path / "protocol" / "custom.toml").write_bytes(
        (ROOT / "protocol" / "custom.toml").read_bytes()
    )
    for source_path, content in expected_artifacts(ROOT, definition).items():
        destination = tmp_path / source_path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)

    changed = tmp_path / relative_path
    changed.write_text(changed.read_text().replace("0x705", "0x702", 1))

    assert stale_artifacts(tmp_path) == (changed,)
