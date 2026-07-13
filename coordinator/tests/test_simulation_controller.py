import pytest
from e87canbus.application.events import SteeringMode
from e87canbus.protocol.can import LED_AMBER, LED_BLUE, LED_OFF, LED_WHITE
from e87canbus.simulation.controller import SimulatorController


def test_initial_snapshot_has_auto_application_state_and_blue_mode_led() -> None:
    controller = SimulatorController()

    snapshot = controller.snapshot()

    assert snapshot.next_pressed is True
    assert snapshot.application.steering_mode is SteeringMode.AUTO
    assert snapshot.led_colours == {0: LED_BLUE, 3: LED_OFF}
    assert snapshot.trace == ()


def test_pressing_button_creates_button_event_frame() -> None:
    controller = SimulatorController()

    snapshot = controller.press_button(0)

    assert snapshot.trace[0].source == "neotrellis"
    assert snapshot.trace[0].frame.arbitration_id == 0x700
    assert snapshot.trace[0].frame.data == b"\x00\x01"


def test_pressing_mode_button_selects_manual_and_causes_amber_led_update() -> None:
    controller = SimulatorController()

    snapshot = controller.press_button(0)

    assert snapshot.trace[1].source == "pi"
    assert snapshot.trace[1].frame.arbitration_id == 0x701
    assert snapshot.trace[1].frame.data == b"\x00\x04"
    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert snapshot.led_colours == {0: LED_AMBER, 3: LED_OFF}


def test_releasing_button_preserves_authoritative_mode_led() -> None:
    controller = SimulatorController()
    controller.press_button(0)

    snapshot = controller.release_button(0)

    assert snapshot.trace[-1].frame.data == b"\x00\x00"
    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert snapshot.led_colours == {0: LED_AMBER, 3: LED_OFF}


def test_reset_clears_trace_and_restores_initial_application_state() -> None:
    controller = SimulatorController()
    controller.press_button(0)

    snapshot = controller.reset()

    assert snapshot.application.steering_mode is SteeringMode.AUTO
    assert snapshot.led_colours == {0: LED_BLUE, 3: LED_OFF}
    assert snapshot.trace == ()


def test_invalid_button_index_raises() -> None:
    controller = SimulatorController(button_count=16)

    with pytest.raises(ValueError, match="button_index"):
        controller.press_button(16)


def test_step_auto_preserves_alternating_behavior() -> None:
    controller = SimulatorController()

    first = controller.step_auto(0)
    second = controller.step_auto(0)

    assert first.trace[0].frame.data == b"\x00\x01"
    assert second.trace[-1].frame.data == b"\x00\x00"


def test_assistance_and_maximum_buttons_run_through_the_simulated_can_slice() -> None:
    controller = SimulatorController()

    snapshot = controller.press_button(2)
    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert snapshot.application.manual_assistance_level == 0

    controller.release_button(2)
    snapshot = controller.press_button(2)
    assert snapshot.application.manual_assistance_level == 1

    controller.release_button(2)
    snapshot = controller.press_button(3)
    assert snapshot.application.maximum_assistance_active is True
    assert snapshot.application.manual_assistance_level == 7
    assert snapshot.led_colours[3] == LED_WHITE

    controller.release_button(3)
    snapshot = controller.press_button(3)
    assert snapshot.application.maximum_assistance_active is False
    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert snapshot.application.manual_assistance_level == 1
    assert snapshot.led_colours[3] == LED_OFF


def test_assistance_button_cancels_maximum_override_through_can_slice() -> None:
    controller = SimulatorController()
    controller.press_button(2)
    controller.release_button(2)
    controller.press_button(2)
    controller.release_button(2)
    controller.press_button(3)
    controller.release_button(3)

    snapshot = controller.press_button(1)

    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert snapshot.application.manual_assistance_level == 1
    assert snapshot.application.maximum_assistance_active is False
    assert snapshot.led_colours[3] == LED_OFF
