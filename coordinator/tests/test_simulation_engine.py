from collections.abc import Callable
from dataclasses import replace

import pytest
from e87canbus.application.events import (
    ButtonPressed,
    SetSteeringAssistance,
    SteeringCommandReason,
)
from e87canbus.application.state import ApplicationState, SteeringMode
from e87canbus.config import CanNetwork, TxPolicyConfig, default_config, simulator_config
from e87canbus.features.steering import ASSISTANCE_QUANTIZATION_TOLERANCE
from e87canbus.protocol.can import CanFrame
from e87canbus.protocol.generated import (
    LED_COLOUR_AMBER,
    LED_COLOUR_BLUE,
    LED_COLOUR_OFF,
    LED_COLOUR_WHITE,
)
from e87canbus.simulation.devices import SimulatedSteeringController
from e87canbus.simulation.engine import (
    PressButton,
    ReleaseButton,
    ResetSimulation,
    RunControlTimer,
    SetVehicleSpeed,
    SilenceVehicleSpeed,
    SimulationEngine,
    SimulationSessionFailed,
    StepButton,
    snapshot_to_dict,
)

TEST_SIMULATOR_CONFIG = replace(
    simulator_config(),
    tx_policy=TxPolicyConfig(
        max_frames_per_network_window=1_000,
    ),
)
OFF_LEDS = (LED_COLOUR_OFF,) * 16
AUTO_LEDS = (LED_COLOUR_BLUE,) + (LED_COLOUR_OFF,) * 15
MANUAL_LEDS = (LED_COLOUR_AMBER,) + (LED_COLOUR_OFF,) * 15
MAXIMUM_LEDS = (
    LED_COLOUR_AMBER,
    LED_COLOUR_OFF,
    LED_COLOUR_OFF,
    LED_COLOUR_WHITE,
) + (LED_COLOUR_OFF,) * 12


def build_test_engine(**kwargs: object) -> SimulationEngine:
    return SimulationEngine(config=TEST_SIMULATOR_CONFIG, **kwargs)


class MutableClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class FailingSteeringController(SimulatedSteeringController):
    def __init__(
        self,
        watchdog_timeout_s: float,
        clock: Callable[[], float],
    ) -> None:
        super().__init__(watchdog_timeout_s, clock)
        self.attempts = 0

    def set_assistance(self, command: SetSteeringAssistance) -> None:
        self.attempts += 1
        if self.attempts >= 2:
            raise OSError(f"actuator failed on attempt {self.attempts}")
        super().set_assistance(command)


class RejectingSteeringController(SimulatedSteeringController):
    def __init__(
        self,
        watchdog_timeout_s: float,
        clock: Callable[[], float],
    ) -> None:
        super().__init__(watchdog_timeout_s, clock)
        self.attempts = 0

    def set_assistance(self, command: SetSteeringAssistance) -> None:
        self.attempts += 1
        raise OSError(f"actuator rejected attempt {self.attempts}")


class RejectingShutdownController(SimulatedSteeringController):
    def __init__(
        self,
        watchdog_timeout_s: float,
        clock: Callable[[], float],
    ) -> None:
        super().__init__(watchdog_timeout_s, clock)
        self.attempts = 0

    def set_assistance(self, command: SetSteeringAssistance) -> None:
        self.attempts += 1
        if command.reason is SteeringCommandReason.SHUTDOWN:
            raise OSError("actuator rejected shutdown")
        super().set_assistance(command)


def test_initial_snapshot_has_auto_application_state_and_blue_mode_led() -> None:
    controller = build_test_engine()

    snapshot = controller.snapshot()

    assert snapshot.next_pressed is True
    assert snapshot.application.speed_valid is False
    assert snapshot.application.steering_mode is SteeringMode.AUTO
    assert snapshot.led_colours == AUTO_LEDS
    assert snapshot.steering_controller.effective_assistance == 0.0
    assert (
        snapshot.steering_controller.last_command_reason
        is SteeringCommandReason.SPEED_NEVER_OBSERVED
    )
    assert snapshot.steering_controller.watchdog_timed_out is False
    assert snapshot.trace == ()


def test_first_startup_command_failure_has_serializable_fatal_snapshot() -> None:
    engine = build_test_engine(steering_controller_factory=RejectingSteeringController)

    snapshot = engine.snapshot()
    serialized = snapshot_to_dict(snapshot, include_trace=True)

    assert (snapshot.revision, snapshot.fatal) == (2, True)
    assert snapshot.steering_controller.effective_assistance == 0.0
    assert snapshot.steering_controller.last_command_reason is None
    assert snapshot.steering_controller.watchdog_timed_out is True
    assert serialized["steering_controller"]["last_command_reason"] is None
    assert engine.steering_controller.attempts == 2


def test_pressing_button_creates_button_event_frame() -> None:
    controller = build_test_engine()

    snapshot = controller.execute(PressButton(0)).snapshot

    assert snapshot.trace[0].source == "neotrellis"
    assert snapshot.trace[0].frame.arbitration_id == 0x700
    assert snapshot.trace[0].frame.data == b"\x00\x01"
    assert snapshot.trace[0].network is CanNetwork.KCAN
    assert snapshot.trace[0].sequence == 1


def test_pressing_mode_button_selects_manual_and_causes_amber_led_snapshot() -> None:
    controller = build_test_engine()

    snapshot = controller.execute(PressButton(0)).snapshot

    assert snapshot.trace[1].source == "pi"
    assert snapshot.trace[1].frame.arbitration_id == 0x701
    assert snapshot.trace[1].frame.data == b"\x04\x00\x00\x00\x00\x00\x00\x00"
    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert snapshot.led_colours == MANUAL_LEDS


def test_releasing_button_preserves_authoritative_mode_led() -> None:
    controller = build_test_engine()
    controller.execute(PressButton(0))

    snapshot = controller.execute(ReleaseButton(0)).snapshot

    assert snapshot.trace[-1].frame.data == b"\x00\x00"
    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert snapshot.led_colours == MANUAL_LEDS


def test_reset_clears_trace_and_restores_initial_application_state() -> None:
    controller = build_test_engine()
    controller.execute(PressButton(0))
    controller.execute(SetVehicleSpeed(42.5))

    snapshot = controller.execute(ResetSimulation()).snapshot

    assert snapshot.application.steering_mode is SteeringMode.AUTO
    assert controller.vehicle.speed_kph is None
    assert (snapshot.session_id, snapshot.revision) == (2, 1)
    assert snapshot.led_colours == AUTO_LEDS
    assert snapshot.trace == ()

    next_snapshot = controller.execute(PressButton(0)).snapshot
    assert next_snapshot.trace[0].sequence == 1


def test_fatal_actuator_failure_stops_session_and_reset_starts_healthy(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = MutableClock()
    controllers: list[FailingSteeringController] = []

    def build_controller(
        watchdog_timeout_s: float,
        controller_clock: Callable[[], float],
    ) -> SimulatedSteeringController:
        controller = FailingSteeringController(watchdog_timeout_s, controller_clock)
        controllers.append(controller)
        return controller

    engine = build_test_engine(
        clock=clock,
        steering_controller_factory=build_controller,
    )

    with caplog.at_level("ERROR"):
        failure_result = engine.execute(RunControlTimer(1.0))
    failed = failure_result.snapshot

    assert failed.fatal is True
    assert failed.revision == engine.kernel.diagnostics().revision == 3
    assert [event["type"] for event in failure_result.events] == ["snapshot"]
    assert engine.kernel.health.steering_actuator_fault is not None
    assert engine.kernel.health.steering_actuator_fault.message == (
        "actuator failed on attempt 2"
    )
    assert controllers[0].attempts == 3
    assert "terminal shutdown effect failed and was discarded" in caplog.text
    assert "attempt 3" in caplog.text
    with pytest.raises(SimulationSessionFailed, match="reset required"):
        engine.execute(PressButton(0))

    reset = engine.execute(ResetSimulation()).snapshot

    assert (reset.session_id, reset.revision, reset.fatal) == (2, 1, False)
    assert reset.revision == engine.kernel.diagnostics().revision


def test_reset_logs_shutdown_failure_and_returns_new_healthy_session(
    caplog: pytest.LogCaptureFixture,
) -> None:
    controllers: list[RejectingShutdownController] = []

    def build_controller(
        watchdog_timeout_s: float,
        clock: Callable[[], float],
    ) -> SimulatedSteeringController:
        controller = RejectingShutdownController(watchdog_timeout_s, clock)
        controllers.append(controller)
        return controller

    engine = build_test_engine(steering_controller_factory=build_controller)

    with caplog.at_level("ERROR"):
        reset = engine.execute(ResetSimulation()).snapshot

    assert controllers[0].attempts == 2
    assert "reset replaced simulation session 1 with fatal diagnostics" in caplog.text
    assert (reset.session_id, reset.revision, reset.fatal) == (2, 1, False)


def test_snapshot_exposes_default_node_membership_on_all_networks() -> None:
    snapshot = build_test_engine().snapshot()

    statuses = {status.config.network: status for status in snapshot.networks}
    assert list(statuses) == [CanNetwork.KCAN, CanNetwork.PTCAN, CanNetwork.FCAN]
    assert statuses[CanNetwork.KCAN].nodes == (
        "pi",
        "simulated-vehicle",
        "neotrellis",
    )
    assert statuses[CanNetwork.PTCAN].nodes == ("pi", "simulated-vehicle")
    assert statuses[CanNetwork.FCAN].nodes == ("pi", "simulated-vehicle")
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
    assert ptcan.nodes == ("simulated-vehicle",)


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
    assert snapshot.led_colours[3] == LED_COLOUR_WHITE

    controller.execute(ReleaseButton(3))
    snapshot = controller.execute(PressButton(3)).snapshot
    assert snapshot.application.maximum_assistance_active is False
    assert snapshot.application.steering_mode is SteeringMode.MANUAL
    assert snapshot.application.manual_assistance_level == 1
    assert snapshot.led_colours[3] == LED_COLOUR_OFF


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
    assert snapshot.led_colours[3] == LED_COLOUR_OFF


def test_timer_publishes_when_it_recovers_a_timed_out_actuator() -> None:
    clock = MutableClock(10.0)
    controller = build_test_engine(clock=clock)

    clock.now = 11.5
    result = controller.execute(RunControlTimer(clock()))

    assert result.snapshot.application.speed_valid is False
    assert [event["type"] for event in result.events] == ["snapshot"]
    assert result.snapshot.steering_controller.watchdog_timed_out is False


def test_timer_publishes_new_manual_actuator_projection() -> None:
    controller = build_test_engine()

    command = controller.execute(PressButton(0))
    timer = controller.execute(RunControlTimer(1.0))

    assert [event["type"] for event in command.events].count("snapshot") == 1
    assert [event["type"] for event in timer.events] == ["snapshot"]
    assert (
        timer.snapshot.steering_controller.last_command_reason
        is SteeringCommandReason.MANUAL
    )


@pytest.mark.parametrize("value", [ButtonPressed(0), ApplicationState()])
def test_engine_rejects_domain_events_and_application_state(value: object) -> None:
    controller = build_test_engine()

    with pytest.raises(TypeError, match="unsupported simulation command"):
        controller.execute(value)  # type: ignore[arg-type]


def test_engine_clock_is_used_for_ingress_and_trace() -> None:
    clock = MutableClock(8.5)
    controller = build_test_engine(clock=clock)

    snapshot = controller.execute(PressButton(0)).snapshot

    assert {entry.monotonic_s for entry in snapshot.trace} == {8.5}


def test_dropped_led_snapshot_is_not_replayed_and_next_snapshot_converges() -> None:
    clock = MutableClock()
    config = replace(
        simulator_config(),
        tx_policy=TxPolicyConfig(
            max_frames_per_network_window=2,
        ),
    )
    controller = SimulationEngine(config=config, clock=clock)

    accepted = controller.execute(PressButton(0)).snapshot
    controller.execute(ReleaseButton(0))
    dropped = controller.execute(PressButton(0)).snapshot

    assert accepted.application.steering_mode is SteeringMode.MANUAL
    assert accepted.led_colours == MANUAL_LEDS
    assert dropped.application.steering_mode is SteeringMode.AUTO
    assert dropped.led_colours == MANUAL_LEDS
    assert [entry.source for entry in dropped.trace].count("pi") == 1

    clock.now = 1.0
    before_next_decision = controller.snapshot()

    assert before_next_decision.led_colours == MANUAL_LEDS
    assert [entry.source for entry in before_next_decision.trace].count("pi") == 1

    converged = controller.execute(PressButton(3)).snapshot

    assert converged.application.maximum_assistance_active is True
    assert converged.led_colours == MAXIMUM_LEDS
    pi_frames = [entry.frame for entry in converged.trace if entry.source == "pi"]
    assert pi_frames == [
        CanFrame(0x701, b"\x04\x00\x00\x00\x00\x00\x00\x00"),
        CanFrame(0x701, b"\x04\x50\x00\x00\x00\x00\x00\x00"),
    ]


def test_startup_and_reset_session_synchronization_each_use_network_budget() -> None:
    config = replace(
        simulator_config(),
        tx_policy=TxPolicyConfig(max_frames_per_network_window=1),
    )
    controller = SimulationEngine(config=config, clock=MutableClock())

    initial = controller.snapshot()
    after_initial_startup = controller.execute(PressButton(0)).snapshot

    assert initial.led_colours == AUTO_LEDS
    assert after_initial_startup.application.steering_mode is SteeringMode.MANUAL
    assert after_initial_startup.led_colours == AUTO_LEDS
    assert all(entry.source != "pi" for entry in after_initial_startup.trace)

    reset = controller.execute(ResetSimulation()).snapshot
    after_reset_startup = controller.execute(PressButton(0)).snapshot

    assert reset.led_colours == AUTO_LEDS
    assert after_reset_startup.application.steering_mode is SteeringMode.MANUAL
    assert after_reset_startup.led_colours == AUTO_LEDS
    assert all(entry.source != "pi" for entry in after_reset_startup.trace)


def test_simulated_speed_uses_can_decode_transition_and_actuator_path() -> None:
    clock = MutableClock(10.0)
    controller = build_test_engine(clock=clock)

    speed = controller.execute(SetVehicleSpeed(15.0)).snapshot
    clock.now = 10.1
    controlled = controller.execute(RunControlTimer(clock())).snapshot

    assert speed.trace[-1].source == "simulated-vehicle"
    assert speed.trace[-1].network is CanNetwork.FCAN
    assert speed.application.vehicle_speed_kph == 15.0
    assert controller.vehicle.speed_kph == 15.0
    assert controlled.steering_controller.effective_assistance == pytest.approx(
        5 / 6, abs=ASSISTANCE_QUANTIZATION_TOLERANCE
    )
    assert controlled.steering_controller.last_command_reason is SteeringCommandReason.AUTO


def test_selected_speed_is_refreshed_before_each_control_timer() -> None:
    clock = MutableClock(1.0)
    controller = build_test_engine(clock=clock)
    controller.execute(SetVehicleSpeed(30.0))

    clock.now = 2.001
    first = controller.execute(RunControlTimer(clock())).snapshot
    clock.now = 3.5
    second = controller.execute(RunControlTimer(clock())).snapshot

    assert [entry.source for entry in second.trace].count("simulated-vehicle") == 3
    assert first.application.speed_valid is True
    assert second.application.speed_valid is True
    assert second.steering_controller.effective_assistance == pytest.approx(
        2 / 3, abs=ASSISTANCE_QUANTIZATION_TOLERANCE
    )
    assert second.steering_controller.last_command_reason is SteeringCommandReason.AUTO


def test_speed_silence_becomes_stale_and_setting_speed_recovers_auto() -> None:
    clock = MutableClock(1.0)
    controller = build_test_engine(clock=clock)
    controller.execute(SetVehicleSpeed(30.0))
    controller.execute(SilenceVehicleSpeed())

    clock.now = 2.001
    stale = controller.execute(RunControlTimer(clock())).snapshot
    controller.execute(SetVehicleSpeed(30.0))
    recovered = controller.execute(RunControlTimer(clock())).snapshot

    assert stale.application.speed_valid is False
    assert stale.steering_controller.effective_assistance == 0.0
    assert stale.steering_controller.last_command_reason is SteeringCommandReason.SPEED_STALE
    assert recovered.application.speed_valid is True
    assert recovered.steering_controller.effective_assistance == pytest.approx(
        2 / 3, abs=ASSISTANCE_QUANTIZATION_TOLERANCE
    )
    assert recovered.steering_controller.last_command_reason is SteeringCommandReason.AUTO


def test_manual_and_maximum_commands_remain_bounded_without_speed() -> None:
    controller = build_test_engine()
    controller.execute(PressButton(0))
    manual = controller.execute(RunControlTimer(0.1)).snapshot
    controller.execute(PressButton(3))
    maximum = controller.execute(RunControlTimer(0.2)).snapshot

    assert manual.steering_controller.effective_assistance == 0.0
    assert manual.steering_controller.last_command_reason is SteeringCommandReason.MANUAL
    assert maximum.steering_controller.effective_assistance == 1.0
    assert maximum.steering_controller.last_command_reason is SteeringCommandReason.MAXIMUM


def test_actuator_watchdog_falls_back_when_coordinator_commands_stop() -> None:
    clock = MutableClock()
    controller = build_test_engine(clock=clock)
    controller.execute(PressButton(3))
    controller.execute(RunControlTimer(clock()))

    clock.now = controller.config.simulation.steering_watchdog_timeout_s + 0.001
    snapshot = controller.snapshot()

    assert snapshot.steering_controller.watchdog_timed_out is True
    assert snapshot.steering_controller.effective_assistance == 0.0
    assert snapshot.steering_controller.last_command_reason is SteeringCommandReason.MAXIMUM
