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


def test_definition_owns_ids_lengths_positions_and_values() -> None:
    definition = load_definition(ROOT / "protocol" / "custom.toml")
    button_event = definition.message("button_event")

    assert definition.protocol_version == 1
    assert len(definition.messages) == 8
    assert button_event.can_id == 0x700
    assert button_event.length == 2
    assert dict(button_event.byte_positions) == {"button_index": 0, "state": 1}
    assert dict(button_event.values) == {"released": 0, "pressed": 1}
    effect = definition.message("button_pad_effect")
    assert effect.can_id == 0x701
    assert effect.length == 8
    assert dict(effect.values) == {
        "blink_red_double": 1,
        "breathe": 2,
        "blink_white_single": 3,
        "blink_amber_double": 4,
    }


def test_registry_messages_have_fixed_ids_and_layouts() -> None:
    definition = load_definition(ROOT / "protocol" / "custom.toml")

    assert [message.can_id for message in definition.messages] == list(range(0x700, 0x708))
    assert all(message.length == 8 for message in definition.messages[2:])
    assert dict(definition.message("button_pad_hello").byte_positions) == {
        "protocol_version": 0,
        "device_id_low": 1,
        "device_id_high": 2,
        "device_session_id_low": 3,
        "device_session_id_high": 4,
        "sequence": 5,
        "reserved_6": 6,
        "reserved_7": 7,
    }
    for suffix in ("hello", "welcome_ack", "heartbeat"):
        button_pad = definition.message(f"button_pad_{suffix}")
        servotronic = definition.message(f"servotronic_controller_{suffix}")
        assert (button_pad.length, button_pad.byte_positions) == (
            servotronic.length,
            servotronic.byte_positions,
        )


def test_markdown_generation_preserves_surrounding_prose() -> None:
    start = "<!-- BEGIN GENERATED CUSTOM PROTOCOL -->"
    end = "<!-- END GENERATED CUSTOM PROTOCOL -->"
    document = f"before\n{start}old{end}\nafter\n"
    generated = f"{start}new{end}"

    assert replace_markdown_section(document, generated) == f"before\n{generated}\nafter\n"


@pytest.mark.parametrize(
    "relative_path",
    [
        Path("coordinator/src/e87canbus/protocol/generated.py"),
        Path("devices/button-pad/include/can_ids.h"),
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
    changed.write_text(changed.read_text().replace("0x700", "0x702", 1))

    assert stale_artifacts(tmp_path) == (changed,)
