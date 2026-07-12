import pytest
from e87canbus.can_io import LED_GREEN, LED_OFF
from e87canbus.sim_controller import SimulatorController


def test_initial_snapshot_has_empty_trace_and_no_leds() -> None:
    controller = SimulatorController()

    snapshot = controller.snapshot()

    assert snapshot.next_pressed is True
    assert snapshot.led_colours == {}
    assert snapshot.trace == ()


def test_pressing_button_creates_button_event_frame() -> None:
    controller = SimulatorController()

    snapshot = controller.press_button(0)

    assert snapshot.trace[0].source == "neotrellis"
    assert snapshot.trace[0].frame.arbitration_id == 0x700
    assert snapshot.trace[0].frame.data == b"\x00\x01"


def test_pressing_button_causes_green_led_update() -> None:
    controller = SimulatorController()

    snapshot = controller.press_button(0)

    assert snapshot.trace[1].source == "pi"
    assert snapshot.trace[1].frame.arbitration_id == 0x701
    assert snapshot.trace[1].frame.data == b"\x00\x02"
    assert snapshot.led_colours == {0: LED_GREEN}


def test_releasing_button_causes_off_led_update() -> None:
    controller = SimulatorController()
    controller.press_button(0)

    snapshot = controller.release_button(0)

    assert snapshot.trace[-2].frame.data == b"\x00\x00"
    assert snapshot.trace[-1].frame.data == b"\x00\x00"
    assert snapshot.led_colours == {0: LED_OFF}


def test_reset_clears_trace_and_led_state() -> None:
    controller = SimulatorController()
    controller.press_button(0)

    snapshot = controller.reset()

    assert snapshot.led_colours == {}
    assert snapshot.trace == ()


def test_invalid_button_index_raises() -> None:
    controller = SimulatorController(button_count=16)

    with pytest.raises(ValueError, match="button_index"):
        controller.press_button(16)


def test_toggle_button_alternates_current_button_state() -> None:
    controller = SimulatorController()

    first = controller.toggle_button(0)
    second = controller.toggle_button(0)

    assert first.trace[0].frame.data == b"\x00\x01"
    assert second.trace[-2].frame.data == b"\x00\x00"


def test_step_auto_preserves_alternating_behavior() -> None:
    controller = SimulatorController()

    first = controller.step_auto(0)
    second = controller.step_auto(0)

    assert first.trace[0].frame.data == b"\x00\x01"
    assert second.trace[-2].frame.data == b"\x00\x00"
