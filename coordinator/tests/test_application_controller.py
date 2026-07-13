from e87canbus.application.controller import ApplicationController
from e87canbus.application.events import (
    ButtonState,
    LedColour,
    NeoTrellisButtonEvent,
    SpeedUpdateEvent,
    SteeringMode,
)
from e87canbus.application.state import RuntimeState
from e87canbus.config import SteeringConfig


def test_initial_state_is_auto_with_blue_mode_led() -> None:
    controller = ApplicationController()

    assert controller.snapshot().steering_mode is SteeringMode.AUTO
    assert controller.desired_outputs()[0].colour is LedColour.BLUE


def test_button_zero_press_toggles_steering_mode_and_led() -> None:
    controller = ApplicationController()

    outputs = controller.handle_event(NeoTrellisButtonEvent(0, ButtonState.PRESSED))

    assert controller.snapshot().steering_mode is SteeringMode.MANUAL
    assert outputs[0].button_index == 0
    assert outputs[0].colour is LedColour.AMBER


def test_button_zero_release_does_not_change_mode() -> None:
    controller = ApplicationController()
    controller.handle_event(NeoTrellisButtonEvent(0, ButtonState.PRESSED))

    outputs = controller.handle_event(NeoTrellisButtonEvent(0, ButtonState.RELEASED))

    assert controller.snapshot().steering_mode is SteeringMode.MANUAL
    assert outputs == ()


def test_second_button_zero_press_returns_to_auto() -> None:
    controller = ApplicationController()
    controller.handle_event(NeoTrellisButtonEvent(0, ButtonState.PRESSED))

    outputs = controller.handle_event(NeoTrellisButtonEvent(0, ButtonState.PRESSED))

    assert controller.snapshot().steering_mode is SteeringMode.AUTO
    assert outputs[0].colour is LedColour.BLUE


def test_unmapped_button_does_not_change_application_state() -> None:
    controller = ApplicationController()

    outputs = controller.handle_event(NeoTrellisButtonEvent(4, ButtonState.PRESSED))

    assert controller.snapshot().steering_mode is SteeringMode.AUTO
    assert outputs == ()


def test_assistance_button_enters_manual_at_remembered_level_then_adjusts() -> None:
    controller = ApplicationController(state=RuntimeState(manual_assistance_level=3))

    outputs = controller.handle_event(NeoTrellisButtonEvent(2, ButtonState.PRESSED))

    assert controller.snapshot().steering_mode is SteeringMode.MANUAL
    assert controller.snapshot().manual_assistance_level == 3
    assert outputs == (controller.desired_outputs()[0],)

    controller.handle_event(NeoTrellisButtonEvent(2, ButtonState.PRESSED))

    assert controller.snapshot().manual_assistance_level == 4


def test_manual_assistance_buttons_clamp_to_configured_bounds() -> None:
    controller = ApplicationController(
        state=RuntimeState(steering_mode=SteeringMode.MANUAL),
        steering_config=SteeringConfig(manual_level_count=3),
    )

    controller.handle_event(NeoTrellisButtonEvent(1, ButtonState.PRESSED))
    assert controller.snapshot().manual_assistance_level == 0

    for _ in range(4):
        controller.handle_event(NeoTrellisButtonEvent(2, ButtonState.PRESSED))
    assert controller.snapshot().manual_assistance_level == 2


def test_maximum_assistance_from_auto_restores_auto_and_remembered_level() -> None:
    controller = ApplicationController(state=RuntimeState(manual_assistance_level=3))

    outputs = controller.handle_event(NeoTrellisButtonEvent(3, ButtonState.PRESSED))

    assert controller.snapshot().steering_mode is SteeringMode.MANUAL
    assert controller.snapshot().manual_assistance_level == 7
    assert controller.snapshot().maximum_assistance_active is True
    assert outputs[1].button_index == 3
    assert outputs[1].colour is LedColour.WHITE

    outputs = controller.handle_event(NeoTrellisButtonEvent(3, ButtonState.PRESSED))

    assert controller.snapshot().steering_mode is SteeringMode.AUTO
    assert controller.snapshot().manual_assistance_level == 3
    assert controller.snapshot().maximum_assistance_active is False
    assert outputs[0].colour is LedColour.BLUE
    assert outputs[1].colour is LedColour.OFF


def test_maximum_assistance_from_manual_restores_previous_manual_level() -> None:
    controller = ApplicationController(
        state=RuntimeState(
            steering_mode=SteeringMode.MANUAL,
            manual_assistance_level=5,
        )
    )

    controller.handle_event(NeoTrellisButtonEvent(3, ButtonState.PRESSED))
    controller.handle_event(NeoTrellisButtonEvent(3, ButtonState.PRESSED))

    assert controller.snapshot().steering_mode is SteeringMode.MANUAL
    assert controller.snapshot().manual_assistance_level == 5


def test_button_releases_do_not_adjust_or_toggle_assistance() -> None:
    controller = ApplicationController()

    for button_index in (1, 2, 3):
        controller.handle_event(
            NeoTrellisButtonEvent(button_index, ButtonState.RELEASED)
        )

    assert controller.snapshot().steering_mode is SteeringMode.AUTO
    assert controller.snapshot().manual_assistance_level == 0
    assert controller.snapshot().maximum_assistance_active is False


def test_speed_event_updates_application_state_without_hardware_output() -> None:
    controller = ApplicationController()

    outputs = controller.handle_event(SpeedUpdateEvent(42.5, "simulated-vehicle"))

    assert controller.snapshot().vehicle_speed_kph == 42.5
    assert outputs == ()
