from dataclasses import replace

import pytest
from e87canbus.application.events import SpeedUpdateEvent, SteeringMode
from e87canbus.config import CanNetwork, TxPolicyConfig, default_config
from e87canbus.protocol.can import LED_AMBER, LED_BLUE, LED_OFF, LED_WHITE, RoutedCanFrame
from e87canbus.simulation.controller import SimulatorController


class MutableClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_initial_snapshot_has_auto_application_state_and_blue_mode_led() -> None:
    controller = SimulatorController()

    snapshot = controller.snapshot()

    assert snapshot.next_pressed is True
    assert snapshot.application.speed_valid is False
    assert snapshot.application.steering_mode is SteeringMode.AUTO
    assert snapshot.led_colours == {0: LED_BLUE, 3: LED_OFF}
    assert snapshot.trace == ()


def test_pressing_button_creates_button_event_frame() -> None:
    controller = SimulatorController()

    snapshot = controller.press_button(0)

    assert snapshot.trace[0].source == "neotrellis"
    assert snapshot.trace[0].frame.arbitration_id == 0x700
    assert snapshot.trace[0].frame.data == b"\x00\x01"
    assert snapshot.trace[0].network is CanNetwork.KCAN
    assert snapshot.trace[0].sequence == 1


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

    next_snapshot = controller.press_button(0)
    assert next_snapshot.trace[0].sequence == 1


def test_snapshot_exposes_default_node_membership_on_all_networks() -> None:
    snapshot = SimulatorController().snapshot()

    statuses = {status.config.network: status for status in snapshot.networks}
    assert list(statuses) == [CanNetwork.KCAN, CanNetwork.PTCAN, CanNetwork.FCAN]
    assert statuses[CanNetwork.KCAN].nodes == (
        "pi",
        "simulated-car",
        "neotrellis",
        "steering-controller",
    )
    assert statuses[CanNetwork.PTCAN].nodes == ("pi", "simulated-car")
    assert statuses[CanNetwork.FCAN].nodes == ("pi", "simulated-car")
    assert all(status.connected for status in statuses.values())


def test_connected_means_coordinator_endpoint_is_attached() -> None:
    config = default_config()
    networks = tuple(
        replace(item, enabled=False) if item.network is CanNetwork.PTCAN else item
        for item in config.can_networks
    )

    snapshot = SimulatorController(config=replace(config, can_networks=networks)).snapshot()

    ptcan = next(
        status for status in snapshot.networks if status.config.network is CanNetwork.PTCAN
    )
    assert ptcan.connected is False
    assert ptcan.nodes == ("simulated-car",)


def test_same_button_id_on_other_networks_does_not_change_application() -> None:
    controller = SimulatorController()
    button_frame = controller.neotrellis.send_button_event(0, True)
    # Drain the real K-CAN event without processing it, then replay its ID on other networks.
    assert controller.pi_buses[CanNetwork.KCAN].receive(timeout_s=0) == button_frame

    controller.runtime.process_frame(
        RoutedCanFrame(CanNetwork.PTCAN, button_frame)
    )
    controller.runtime.process_frame(
        RoutedCanFrame(CanNetwork.FCAN, button_frame)
    )

    assert controller.application.snapshot().steering_mode is SteeringMode.AUTO


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


def test_controller_tick_uses_shared_clock_and_records_snapshot_event() -> None:
    clock = MutableClock(10.0)
    controller = SimulatorController(clock=clock)
    controller.application.handle_event(
        SpeedUpdateEvent(42.0, CanNetwork.FCAN), clock()
    )

    clock.now = 11.5
    snapshot = controller.tick()

    assert snapshot.application.speed_valid is False
    assert controller.last_events[0]["type"] == "snapshot"


def test_controller_clock_is_used_for_runtime_health_and_trace() -> None:
    clock = MutableClock(8.5)
    controller = SimulatorController(clock=clock)

    snapshot = controller.press_button(0)

    health = controller.application.state.can_health.latest_rx_monotonic_s
    assert health[CanNetwork.KCAN] == 8.5
    assert {entry.monotonic_s for entry in snapshot.trace} == {8.5}


def test_coordinator_tx_budget_drops_led_replies_without_dropping_button_events() -> None:
    clock = MutableClock()
    config = replace(
        default_config(),
        tx_policy=TxPolicyConfig(min_id_gap_s=0.0, max_frames_per_s=3),
    )
    controller = SimulatorController(config=config, clock=clock)

    for _ in range(4):
        controller.press_button(0)
        snapshot = controller.release_button(0)

    sources = [entry.source for entry in snapshot.trace]
    assert sources.count("neotrellis") == 8
    assert sources.count("pi") == 1
