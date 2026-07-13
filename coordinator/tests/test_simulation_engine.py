from dataclasses import replace

import pytest
from e87canbus.application.events import ButtonPressed
from e87canbus.application.state import ApplicationState, SteeringMode
from e87canbus.can_io import CanEndpoint
from e87canbus.config import CanNetwork, TxPolicyConfig, default_config, simulator_config
from e87canbus.protocol.can import (
    LED_AMBER,
    LED_BLUE,
    LED_OFF,
    LED_WHITE,
    ArduinoButtonEventPayload,
    encode_button_event,
)
from e87canbus.runtime import ReceivedCanFrame
from e87canbus.simulation.engine import (
    MAX_CASCADE_PASSES,
    PressButton,
    ReleaseButton,
    ResetSimulation,
    RunControlTimer,
    SimulationEngine,
    StepButton,
)

TEST_SIMULATOR_CONFIG = replace(
    simulator_config(),
    tx_policy=TxPolicyConfig(
        max_frames_per_network_window=1_000,
    ),
)


def build_test_engine(**kwargs: object) -> SimulationEngine:
    return SimulationEngine(config=TEST_SIMULATOR_CONFIG, **kwargs)


class MutableClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class ReactiveSteeringController:
    def __init__(self, bus: CanEndpoint, *, reply_once: bool) -> None:
        self.bus = bus
        self.reply_once = reply_once
        self.replied = False

    def drain_pending(self) -> int:
        drained = 0
        while self.bus.receive(timeout_s=0) is not None:
            drained += 1
        if drained and (not self.reply_once or not self.replied):
            self.bus.send(
                encode_button_event(
                    ArduinoButtonEventPayload(button_index=0, pressed=True),
                    default_config().custom_can_ids,
                )
            )
            self.replied = True
        return drained

def test_initial_snapshot_has_auto_application_state_and_blue_mode_led() -> None:
    controller = build_test_engine()

    snapshot = controller.snapshot()

    assert snapshot.next_pressed is True
    assert snapshot.application.speed_valid is False
    assert snapshot.application.steering_mode is SteeringMode.AUTO
    assert snapshot.led_colours == {0: LED_BLUE, 3: LED_OFF}
    assert snapshot.trace == ()


def test_pressing_button_creates_button_event_frame() -> None:
    controller = build_test_engine()

    snapshot = controller.execute(PressButton(0)).snapshot

    assert snapshot.trace[0].source == "neotrellis"
    assert snapshot.trace[0].frame.arbitration_id == 0x700
    assert snapshot.trace[0].frame.data == b"\x00\x01"
    assert snapshot.trace[0].network is CanNetwork.KCAN
    assert snapshot.trace[0].sequence == 1


def test_pressing_mode_button_selects_manual_and_causes_amber_led_update() -> None:
    controller = build_test_engine()

    snapshot = controller.execute(PressButton(0)).snapshot

    assert snapshot.trace[1].source == "pi"
    assert snapshot.trace[1].frame.arbitration_id == 0x701
    assert snapshot.trace[1].frame.data == b"\x00\x04"
    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert snapshot.led_colours == {0: LED_AMBER, 3: LED_OFF}


def test_releasing_button_preserves_authoritative_mode_led() -> None:
    controller = build_test_engine()
    controller.execute(PressButton(0))

    snapshot = controller.execute(ReleaseButton(0)).snapshot

    assert snapshot.trace[-1].frame.data == b"\x00\x00"
    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert snapshot.led_colours == {0: LED_AMBER, 3: LED_OFF}


def test_reset_clears_trace_and_restores_initial_application_state() -> None:
    controller = build_test_engine()
    controller.execute(PressButton(0))

    snapshot = controller.execute(ResetSimulation()).snapshot

    assert snapshot.application.steering_mode is SteeringMode.AUTO
    assert (snapshot.session_id, snapshot.revision) == (2, 1)
    assert snapshot.led_colours == {0: LED_BLUE, 3: LED_OFF}
    assert snapshot.trace == ()

    next_snapshot = controller.execute(PressButton(0)).snapshot
    assert next_snapshot.trace[0].sequence == 1


def test_snapshot_exposes_default_node_membership_on_all_networks() -> None:
    snapshot = build_test_engine().snapshot()

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

    snapshot = SimulationEngine(config=replace(config, can_networks=networks)).snapshot()

    ptcan = next(
        status for status in snapshot.networks if status.config.network is CanNetwork.PTCAN
    )
    assert ptcan.connected is False
    assert ptcan.nodes == ("simulated-car",)


def test_same_button_id_on_other_networks_does_not_change_application() -> None:
    clock = MutableClock(3.0)
    controller = build_test_engine(clock=clock)
    button_frame = controller.neotrellis.send_button_event(0, True)
    # Drain the real K-CAN event without processing it, then replay its ID on other networks.
    assert controller.pi_buses[CanNetwork.KCAN].receive(timeout_s=0) == button_frame

    controller.kernel.dispatch(
        ReceivedCanFrame(CanNetwork.PTCAN, button_frame, received_at=clock())
    )
    controller.kernel.dispatch(
        ReceivedCanFrame(CanNetwork.FCAN, button_frame, received_at=clock())
    )

    assert controller.kernel.snapshot().steering_mode is SteeringMode.AUTO


def test_invalid_button_index_raises() -> None:
    controller = build_test_engine(button_count=16)

    with pytest.raises(ValueError, match="button_index"):
        controller.execute(PressButton(16))


def test_step_auto_preserves_alternating_behavior() -> None:
    controller = build_test_engine()

    first = controller.execute(StepButton(0)).snapshot
    second = controller.execute(StepButton(0)).snapshot

    assert first.trace[0].frame.data == b"\x00\x01"
    assert second.trace[-1].frame.data == b"\x00\x00"


def test_assistance_and_maximum_buttons_run_through_the_simulated_can_slice() -> None:
    controller = build_test_engine()

    snapshot = controller.execute(PressButton(2)).snapshot
    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert snapshot.application.manual_assistance_level == 0

    controller.execute(ReleaseButton(2))
    snapshot = controller.execute(PressButton(2)).snapshot
    assert snapshot.application.manual_assistance_level == 1

    controller.execute(ReleaseButton(2))
    snapshot = controller.execute(PressButton(3)).snapshot
    assert snapshot.application.maximum_assistance_active is True
    assert snapshot.application.manual_assistance_level == 7
    assert snapshot.led_colours[3] == LED_WHITE

    controller.execute(ReleaseButton(3))
    snapshot = controller.execute(PressButton(3)).snapshot
    assert snapshot.application.maximum_assistance_active is False
    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert snapshot.application.manual_assistance_level == 1
    assert snapshot.led_colours[3] == LED_OFF


def test_assistance_button_cancels_maximum_override_through_can_slice() -> None:
    controller = build_test_engine()
    controller.execute(PressButton(2))
    controller.execute(ReleaseButton(2))
    controller.execute(PressButton(2))
    controller.execute(ReleaseButton(2))
    controller.execute(PressButton(3))
    controller.execute(ReleaseButton(3))

    snapshot = controller.execute(PressButton(1)).snapshot

    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert snapshot.application.manual_assistance_level == 1
    assert snapshot.application.maximum_assistance_active is False
    assert snapshot.led_colours[3] == LED_OFF


def test_unchanged_control_timer_does_not_publish_snapshot() -> None:
    clock = MutableClock(10.0)
    controller = build_test_engine(clock=clock)

    clock.now = 11.5
    result = controller.execute(RunControlTimer(clock()))

    assert result.snapshot.application.speed_valid is False
    assert result.events == ()


def test_command_then_unchanged_timer_produces_one_snapshot_publication() -> None:
    controller = build_test_engine()

    command = controller.execute(PressButton(0))
    timer = controller.execute(RunControlTimer(1.0))

    assert [event["type"] for event in command.events].count("snapshot") == 1
    assert timer.events == ()


@pytest.mark.parametrize("value", [ButtonPressed(0), ApplicationState()])
def test_engine_rejects_domain_events_and_application_state(value: object) -> None:
    controller = build_test_engine()

    with pytest.raises(TypeError, match="unsupported simulation command"):
        controller.execute(value)  # type: ignore[arg-type]


def test_engine_clock_is_used_for_runtime_health_and_trace() -> None:
    clock = MutableClock(8.5)
    controller = build_test_engine(clock=clock)

    snapshot = controller.execute(PressButton(0)).snapshot

    health = controller.kernel.health
    assert health.for_network(CanNetwork.KCAN).latest_rx_monotonic_s == 8.5
    assert {entry.monotonic_s for entry in snapshot.trace} == {8.5}


def test_coordinator_tx_budget_drops_led_replies_without_dropping_button_events() -> None:
    clock = MutableClock()
    config = replace(
        simulator_config(),
        tx_policy=TxPolicyConfig(
            max_frames_per_network_window=3,
        ),
    )
    controller = SimulationEngine(config=config, clock=clock)

    for _ in range(4):
        controller.execute(PressButton(0))
        snapshot = controller.execute(ReleaseButton(0)).snapshot

    sources = [entry.source for entry in snapshot.trace]
    assert sources.count("neotrellis") == 8
    assert sources.count("pi") == 1


def test_reactive_device_cascade_is_processed_in_one_command() -> None:
    controller = build_test_engine()
    controller.steering_controller = ReactiveSteeringController(
        controller.steering_controller.bus,
        reply_once=True,
    )

    result = controller.execute(PressButton(15))
    snapshot = result.snapshot

    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert any(entry.source == "steering-controller" for entry in snapshot.trace)
    assert snapshot.led_colours[0] == LED_AMBER


def test_reactive_device_livelock_warns_and_returns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = replace(
        simulator_config(),
        tx_policy=TxPolicyConfig(
            max_frames_per_network_window=1_000,
        ),
    )
    controller = SimulationEngine(config=config)
    controller.steering_controller = ReactiveSteeringController(
        controller.steering_controller.bus,
        reply_once=False,
    )

    snapshot = controller.execute(PressButton(15)).snapshot

    assert snapshot.trace
    assert (
        f"simulation did not quiesce after {MAX_CASCADE_PASSES} passes"
        in caplog.text
    )
