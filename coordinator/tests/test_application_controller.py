from dataclasses import FrozenInstanceError

import pytest
from e87canbus.application.controller import ApplicationController, ApplicationSnapshot
from e87canbus.application.events import (
    ButtonState,
    LedColour,
    NeoTrellisButtonEvent,
    SpeedUpdateEvent,
    SteeringMode,
)
from e87canbus.application.state import ApplicationState, NormalSteering
from e87canbus.config import CanNetwork, SteeringConfig


def application_state(
    mode: SteeringMode = SteeringMode.AUTO,
    manual_level: int = 0,
) -> ApplicationState:
    return ApplicationState(steering=NormalSteering(mode, manual_level))


def press(controller: ApplicationController, button_index: int) -> tuple[LedColour, ...]:
    outputs = controller.handle_event(
        NeoTrellisButtonEvent(button_index, ButtonState.PRESSED), 0.0
    )
    return tuple(output.colour for output in outputs)


def steering_projection(snapshot: ApplicationSnapshot) -> tuple[SteeringMode, int, bool]:
    return (
        snapshot.steering_mode,
        snapshot.manual_assistance_level,
        snapshot.maximum_assistance_active,
    )


def test_initial_snapshot_and_desired_outputs() -> None:
    controller = ApplicationController()

    assert controller.snapshot() == ApplicationSnapshot(
        vehicle_speed_kph=0.0,
        steering_mode=SteeringMode.AUTO,
        manual_assistance_level=0,
        maximum_assistance_active=False,
        speed_valid=False,
    )
    assert tuple(output.colour for output in controller.desired_outputs()) == (
        LedColour.BLUE,
        LedColour.OFF,
    )


@pytest.mark.parametrize(
    ("initial_mode", "button_index", "expected", "output_colours"),
    [
        (SteeringMode.AUTO, 0, (SteeringMode.MANUAL, 0, False), (LedColour.AMBER,)),
        (SteeringMode.AUTO, 1, (SteeringMode.MANUAL, 0, False), (LedColour.AMBER,)),
        (SteeringMode.AUTO, 2, (SteeringMode.MANUAL, 0, False), (LedColour.AMBER,)),
        (
            SteeringMode.AUTO,
            3,
            (SteeringMode.MANUAL, 7, True),
            (LedColour.AMBER, LedColour.WHITE),
        ),
        (SteeringMode.MANUAL, 0, (SteeringMode.AUTO, 0, False), (LedColour.BLUE,)),
        (SteeringMode.MANUAL, 1, (SteeringMode.MANUAL, 0, False), ()),
        (SteeringMode.MANUAL, 2, (SteeringMode.MANUAL, 1, False), ()),
        (
            SteeringMode.MANUAL,
            3,
            (SteeringMode.MANUAL, 7, True),
            (LedColour.AMBER, LedColour.WHITE),
        ),
    ],
)
def test_mapped_buttons_from_normal_modes(
    initial_mode: SteeringMode,
    button_index: int,
    expected: tuple[SteeringMode, int, bool],
    output_colours: tuple[LedColour, ...],
) -> None:
    controller = ApplicationController(state=application_state(mode=initial_mode))

    colours = press(controller, button_index)

    assert steering_projection(controller.snapshot()) == expected
    assert colours == output_colours


@pytest.mark.parametrize(
    ("button_index", "expected", "output_colours"),
    [
        (0, (SteeringMode.MANUAL, 7, True), ()),
        (1, (SteeringMode.MANUAL, 3, False), (LedColour.AMBER, LedColour.OFF)),
        (2, (SteeringMode.MANUAL, 3, False), (LedColour.AMBER, LedColour.OFF)),
        (3, (SteeringMode.AUTO, 3, False), (LedColour.BLUE, LedColour.OFF)),
    ],
)
def test_mapped_buttons_while_maximum_assistance_is_active(
    button_index: int,
    expected: tuple[SteeringMode, int, bool],
    output_colours: tuple[LedColour, ...],
) -> None:
    controller = ApplicationController(state=application_state(manual_level=3))
    press(controller, 3)

    colours = press(controller, button_index)

    assert steering_projection(controller.snapshot()) == expected
    assert colours == output_colours


def test_maximum_assistance_restores_previous_manual_state() -> None:
    controller = ApplicationController(
        state=application_state(mode=SteeringMode.MANUAL, manual_level=5)
    )

    press(controller, 3)
    press(controller, 3)

    assert steering_projection(controller.snapshot()) == (
        SteeringMode.MANUAL,
        5,
        False,
    )


def test_first_assistance_press_after_maximum_does_not_adjust_restored_level() -> None:
    controller = ApplicationController(state=application_state(manual_level=3))
    press(controller, 3)

    press(controller, 2)
    assert controller.snapshot().manual_assistance_level == 3

    press(controller, 2)
    assert controller.snapshot().manual_assistance_level == 4


@pytest.mark.parametrize(
    "event",
    [
        NeoTrellisButtonEvent(0, ButtonState.RELEASED),
        NeoTrellisButtonEvent(3, ButtonState.RELEASED),
        NeoTrellisButtonEvent(9, ButtonState.PRESSED),
    ],
)
def test_release_and_unknown_button_events_are_no_ops(event: NeoTrellisButtonEvent) -> None:
    controller = ApplicationController()
    before = controller.snapshot()

    outputs = controller.handle_event(event, 0.0)

    assert outputs == ()
    assert controller.snapshot() == before


def test_manual_assistance_is_clamped_to_configured_bounds() -> None:
    controller = ApplicationController(
        state=application_state(mode=SteeringMode.MANUAL, manual_level=-4),
        steering_config=SteeringConfig(manual_level_count=3),
    )

    press(controller, 1)
    assert controller.snapshot().manual_assistance_level == 0

    for _ in range(4):
        press(controller, 2)
    assert controller.snapshot().manual_assistance_level == 2


@pytest.mark.parametrize(
    ("evaluation_time", "expected_valid"),
    [(10.5, True), (11.0, True), (11.000_001, False)],
)
def test_speed_validity_is_derived_from_sample_age(
    evaluation_time: float,
    expected_valid: bool,
) -> None:
    controller = ApplicationController()
    controller.handle_event(SpeedUpdateEvent(42.5, CanNetwork.FCAN), 10.0)

    controller.tick(evaluation_time)

    snapshot = controller.snapshot()
    assert snapshot.vehicle_speed_kph == 42.5
    assert snapshot.speed_valid is expected_valid


def test_speed_is_invalid_before_any_sample() -> None:
    controller = ApplicationController()

    controller.tick(100.0)

    assert controller.snapshot().vehicle_speed_kph == 0.0
    assert controller.snapshot().speed_valid is False


def test_speed_sample_clamps_negative_speed_and_retains_observation() -> None:
    controller = ApplicationController()

    outputs = controller.handle_event(SpeedUpdateEvent(-2.0, CanNetwork.PTCAN), 12.5)

    sample = controller.state.speed_sample
    assert sample is not None
    assert sample.speed_kph == 0.0
    assert sample.observed_at == 12.5
    assert sample.source_network is CanNetwork.PTCAN
    assert controller.snapshot().speed_valid is True
    assert outputs == ()


def test_state_is_frozen_and_replaced_atomically() -> None:
    controller = ApplicationController()
    before = controller.state

    press(controller, 0)

    assert controller.state is not before
    assert steering_projection(controller.snapshot()) == (
        SteeringMode.MANUAL,
        0,
        False,
    )
    with pytest.raises(FrozenInstanceError):
        before.speed_evaluated_at = 1.0  # type: ignore[misc]
