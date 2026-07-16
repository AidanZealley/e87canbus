import gc
import weakref
from collections.abc import Callable
from dataclasses import replace

import pytest
from e87canbus.application.controller import EngineTelemetryStatus, EngineTelemetryValue
from e87canbus.application.events import (
    ButtonPressed,
    LedColour,
    SetSteeringAssistance,
    SteeringCommandReason,
)
from e87canbus.application.state import ApplicationState, SteeringMode
from e87canbus.config import (
    CanNetwork,
    HighBeamStrobeConfig,
    TxPolicyConfig,
    default_config,
    simulator_config,
)
from e87canbus.device import DeviceRole, DeviceSource
from e87canbus.features.steering import ASSISTANCE_QUANTIZATION_TOLERANCE
from e87canbus.protocol.can import (
    CanFrame,
    DeviceHeartbeatPayload,
    DeviceHelloPayload,
    decode_heartbeat,
    decode_hello,
    decode_welcome_ack,
    encode_heartbeat,
    encode_hello,
)
from e87canbus.protocol.generated import LED_COUNT
from e87canbus.runtime import ReceivedCanFrame, SetMaximumAssistance
from e87canbus.service import ControllerWorkUnavailable
from e87canbus.simulation.devices import SimulatedDeviceState, SimulatedServotronicPeer
from e87canbus.simulation.protocol import (
    SIMULATION_ONLY_COOLANT_TEMPERATURE_ID,
    SIMULATION_ONLY_ENGINE_RPM_ID,
    SIMULATION_ONLY_HIGH_BEAM_COMMAND_ID,
    SIMULATION_ONLY_OIL_TEMPERATURE_ID,
)
from e87canbus.simulation.runtime import (
    ConnectSimulatedDevice,
    DisconnectSimulatedDevice,
    PressButton,
    RebootSimulatedDevice,
    ReleaseButton,
    ResetSimulation,
    RunControlTimer,
    SetCoolantTemperature,
    SetEngineRpm,
    SetOilTemperature,
    SetSimulatedDeviceProtocolVersion,
    SetSimulatedDeviceStatusCode,
    SetVehicleSpeed,
    SilenceOilTemperature,
    SilenceVehicleSpeed,
    SimulatedControllerRuntime,
    TapButton,
)

TEST_SIMULATOR_CONFIG = replace(
    simulator_config(),
    tx_policy=TxPolicyConfig(
        max_frames_per_network_window=1_000,
    ),
)
AUTO_LEDS = (LedColour.BLUE,) + (LedColour.OFF,) * (LED_COUNT - 1)
MANUAL_LEDS = (LedColour.AMBER,) + (LedColour.OFF,) * (LED_COUNT - 1)
MAXIMUM_LEDS = (
    LedColour.AMBER,
    LedColour.OFF,
    LedColour.OFF,
    LedColour.WHITE,
) + (LedColour.OFF,) * (LED_COUNT - 4)


def build_test_engine(**kwargs: object) -> SimulatedControllerRuntime:
    runtime = SimulatedControllerRuntime(config=TEST_SIMULATOR_CONFIG, **kwargs)
    runtime.start()
    inject_registry_frames(runtime)
    return runtime


def inject_registry_frames(runtime: SimulatedControllerRuntime) -> None:
    ids = runtime.config.custom_can_ids
    now = runtime._clock()
    roles = (
        (
            DeviceRole.BUTTON_PAD,
            ids.button_pad_hello,
            ids.button_pad_heartbeat,
        ),
        (
            DeviceRole.SERVOTRONIC_CONTROLLER,
            ids.servotronic_controller_hello,
            ids.servotronic_controller_heartbeat,
        ),
    )
    for role, hello_id, heartbeat_id in roles:
        if role is DeviceRole.BUTTON_PAD and runtime.button_pad_source is DeviceSource.DISABLED:
            continue
        runtime.execute(
            ReceivedCanFrame(
                CanNetwork.KCAN,
                encode_hello(DeviceHelloPayload(1, 1, 1, 0), hello_id),
                now,
            )
        )
        if runtime.kernel.health.fatal:
            break
        runtime.execute(
            ReceivedCanFrame(
                CanNetwork.KCAN,
                encode_heartbeat(
                    DeviceHeartbeatPayload(
                        1,
                        1,
                        runtime.kernel.controller_session_id,
                        0,
                        0,
                    ),
                    heartbeat_id,
                ),
                now,
            )
        )
        if runtime.kernel.health.fatal:
            break
    runtime.topology.clear_trace()


def application(runtime: SimulatedControllerRuntime):
    return runtime.projection()[0]


def diagnostics(runtime: SimulatedControllerRuntime):
    return runtime.projection()[1]


def adapter(runtime: SimulatedControllerRuntime):
    return runtime.projection()[2]


class MutableClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def build_handshake_engine() -> tuple[SimulatedControllerRuntime, MutableClock]:
    clock = MutableClock()
    runtime = SimulatedControllerRuntime(config=TEST_SIMULATOR_CONFIG, clock=clock)
    runtime.start()
    return runtime, clock


def registry_status(runtime: SimulatedControllerRuntime, role: DeviceRole) -> str:
    return runtime.kernel.registry_for(role).status.value


class FailingServotronicPeer(SimulatedServotronicPeer):
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


class RejectingServotronicPeer(SimulatedServotronicPeer):
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


class RejectingShutdownPeer(SimulatedServotronicPeer):
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


def test_virtual_peers_register_and_send_immediate_first_heartbeat() -> None:
    runtime, clock = build_handshake_engine()
    ids = runtime.config.custom_can_ids

    first = runtime.deadline(clock())

    assert {registry_status(runtime, role) for role in DeviceRole} == {"active"}
    assert {event["arbitration_id"] for event in first.events} >= {
        ids.button_pad_hello,
        ids.button_pad_welcome_ack,
        ids.button_pad_heartbeat,
        ids.servotronic_controller_hello,
        ids.servotronic_controller_welcome_ack,
        ids.servotronic_controller_heartbeat,
    }
    for role, hello_id, acknowledgement_id in (
        (DeviceRole.BUTTON_PAD, ids.button_pad_hello, ids.button_pad_welcome_ack),
        (
            DeviceRole.SERVOTRONIC_CONTROLLER,
            ids.servotronic_controller_hello,
            ids.servotronic_controller_welcome_ack,
        ),
    ):
        del role
        hello_frame = next(
            entry.frame
            for entry in runtime.topology.trace()
            if entry.frame.arbitration_id == hello_id
        )
        acknowledgement_frame = next(
            entry.frame
            for entry in runtime.topology.trace()
            if entry.frame.arbitration_id == acknowledgement_id
        )
        hello = decode_hello(hello_frame, hello_id)
        acknowledgement = decode_welcome_ack(acknowledgement_frame, acknowledgement_id)
        assert hello is not None
        assert acknowledgement is not None
        assert hello.device_id == 1
        assert acknowledgement.device_session_id == hello.device_session_id
        assert acknowledgement.device_sequence == hello.sequence

    for role, heartbeat_id, acknowledgement_id in (
        (DeviceRole.BUTTON_PAD, ids.button_pad_heartbeat, ids.button_pad_welcome_ack),
        (
            DeviceRole.SERVOTRONIC_CONTROLLER,
            ids.servotronic_controller_heartbeat,
            ids.servotronic_controller_welcome_ack,
        ),
    ):
        del role
        heartbeat_frame = next(
            entry.frame
            for entry in runtime.topology.trace()
            if entry.frame.arbitration_id == heartbeat_id
        )
        acknowledgement_frame = [
            entry.frame
            for entry in runtime.topology.trace()
            if entry.frame.arbitration_id == acknowledgement_id
        ][-1]
        heartbeat = decode_heartbeat(heartbeat_frame, heartbeat_id)
        acknowledgement = decode_welcome_ack(acknowledgement_frame, acknowledgement_id)
        assert heartbeat is not None
        assert acknowledgement is not None
        assert heartbeat.status == 0
        assert acknowledgement.device_sequence == heartbeat.sequence


def test_disconnect_expires_lease_reconnects_and_reboots_with_new_sessions() -> None:
    runtime, clock = build_handshake_engine()
    runtime.deadline(clock())
    clock.now = 1.0
    runtime.deadline(clock())
    peer = runtime.neotrellis
    assert peer is not None
    original_session = peer.session_id

    runtime.execute(DisconnectSimulatedDevice(DeviceRole.BUTTON_PAD))
    assert registry_status(runtime, DeviceRole.BUTTON_PAD) == "active"

    clock.now = 4.0
    runtime.deadline(clock())
    assert registry_status(runtime, DeviceRole.BUTTON_PAD) == "stale"

    runtime.execute(ConnectSimulatedDevice(DeviceRole.BUTTON_PAD))
    assert peer.session_id != original_session
    assert registry_status(runtime, DeviceRole.BUTTON_PAD) == "active"

    connected_session = peer.session_id
    runtime.execute(RebootSimulatedDevice(DeviceRole.BUTTON_PAD))
    assert peer.session_id != connected_session
    assert registry_status(runtime, DeviceRole.BUTTON_PAD) == "active"


def test_ack_loss_enters_controller_lost_and_connect_restarts_a_connected_peer() -> None:
    runtime, clock = build_handshake_engine()
    runtime.deadline(clock())
    clock.now = 1.0
    runtime.deadline(clock())
    peer = runtime.servotronic
    assert peer.bus is not None
    original_process_pending = peer.process_pending

    def discard_acknowledgements(now: float, *, limit: int = 64) -> int:
        del now
        processed = 0
        while processed < limit and peer.bus.receive(timeout_s=0) is not None:
            processed += 1
        return processed

    peer.process_pending = discard_acknowledgements  # type: ignore[method-assign]
    clock.now = 4.0
    runtime.deadline(clock())

    assert peer.connected is True
    assert peer.state is SimulatedDeviceState.CONTROLLER_LOST
    assert registry_status(runtime, DeviceRole.SERVOTRONIC_CONTROLLER) == "pending"
    lost_session = peer.session_id

    runtime.execute(ConnectSimulatedDevice(DeviceRole.SERVOTRONIC_CONTROLLER))
    assert peer.session_id != lost_session
    assert peer.state is SimulatedDeviceState.DISCOVERING
    assert registry_status(runtime, DeviceRole.SERVOTRONIC_CONTROLLER) == "pending"

    peer.process_pending = original_process_pending  # type: ignore[method-assign]
    clock.now = 5.0
    runtime.deadline(clock())
    assert registry_status(runtime, DeviceRole.SERVOTRONIC_CONTROLLER) == "active"


def test_incompatible_retry_fault_recovery_and_reset_restore_healthy_peers() -> None:
    runtime, clock = build_handshake_engine()
    runtime.deadline(clock())
    clock.now = 1.0
    runtime.deadline(clock())
    peer = runtime.servotronic
    session_before_incompatible = peer.session_id

    runtime.execute(
        SetSimulatedDeviceProtocolVersion(DeviceRole.SERVOTRONIC_CONTROLLER, 2)
    )
    assert peer.session_id != session_before_incompatible
    assert registry_status(runtime, DeviceRole.SERVOTRONIC_CONTROLLER) == "incompatible"
    retry_trace_before = len(runtime.topology.trace())
    clock.now = 6.0
    runtime.deadline(clock())
    assert registry_status(runtime, DeviceRole.SERVOTRONIC_CONTROLLER) == "incompatible"
    assert len(runtime.topology.trace()) > retry_trace_before

    runtime.execute(
        SetSimulatedDeviceProtocolVersion(DeviceRole.SERVOTRONIC_CONTROLLER, 1)
    )
    assert registry_status(runtime, DeviceRole.SERVOTRONIC_CONTROLLER) == "active"

    runtime.execute(SetSimulatedDeviceStatusCode(DeviceRole.SERVOTRONIC_CONTROLLER, 7))
    clock.now = 8.0
    runtime.deadline(clock())
    assert registry_status(runtime, DeviceRole.SERVOTRONIC_CONTROLLER) == "fault"
    assert runtime.kernel.registry_for(DeviceRole.SERVOTRONIC_CONTROLLER).last_status_code == 7

    runtime.execute(SetSimulatedDeviceStatusCode(DeviceRole.SERVOTRONIC_CONTROLLER, 0))
    clock.now = 9.0
    runtime.deadline(clock())
    assert registry_status(runtime, DeviceRole.SERVOTRONIC_CONTROLLER) == "active"
    assert runtime.kernel.registry_for(DeviceRole.SERVOTRONIC_CONTROLLER).last_status_code == 0

    runtime.execute(ResetSimulation())
    assert runtime.neotrellis is not None
    assert all(peer.connected for peer in (runtime.neotrellis, runtime.servotronic))
    assert all(
        peer.protocol_version == 1 and peer.status_code == 0
        for peer in (runtime.neotrellis, runtime.servotronic)
    )
    assert all(
        peer.state is SimulatedDeviceState.DISCOVERING
        for peer in (runtime.neotrellis, runtime.servotronic)
    )
    assert {registry_status(runtime, role) for role in DeviceRole} == {"not_found"}


def test_initial_snapshot_has_auto_application_state_and_blue_mode_led() -> None:
    controller = build_test_engine()

    current_application = application(controller)
    current_adapter = adapter(controller)

    assert current_application.speed_valid is False
    assert current_application.engine.rpm.status is EngineTelemetryStatus.NEVER_OBSERVED
    assert current_application.engine.rpm.value is None
    assert current_application.steering_mode is SteeringMode.AUTO
    assert current_application.button_led_colours == AUTO_LEDS
    assert current_adapter.servotronic is not None
    assert current_adapter.servotronic.effective_assistance == 0.0
    assert (
        current_adapter.servotronic.last_command_reason
        == SteeringCommandReason.SPEED_NEVER_OBSERVED.value
    )
    assert current_adapter.servotronic.watchdog_timed_out is False
    assert len(current_adapter.registry) == 2
    button_pad = next(
        entry for entry in current_adapter.registry if entry.role is DeviceRole.BUTTON_PAD
    )
    assert button_pad.source_mode is DeviceSource.EMULATED
    assert button_pad.status.value == "active"
    assert controller.topology.trace() == ()


@pytest.mark.parametrize("source", [DeviceSource.DISABLED])
def test_non_emulated_roles_cannot_emit_button_input(source: DeviceSource) -> None:
    controller = build_test_engine(button_pad_source=source)

    with pytest.raises(ControllerWorkUnavailable, match="emulated source role"):
        controller.execute(PressButton(0))

    assert application(controller).steering_mode is SteeringMode.AUTO
    assert "button-pad-emulator" not in adapter(controller).networks[0].nodes


def test_emulator_failure_is_reported_without_claiming_physical_health() -> None:
    controller = build_test_engine()
    emulator = controller.neotrellis
    assert emulator is not None

    def fail() -> list[object]:
        raise OSError("emulator decoder failed")

    emulator.process_pending_led_snapshots = fail  # type: ignore[method-assign]
    controller.execute(SetMaximumAssistance(True))

    fault = controller.kernel.health.devices[0].fault
    assert fault is not None
    assert fault.message == "emulator decoder failed"
    assert diagnostics(controller).health.fatal is False
    button_pad = next(
        entry
        for entry in adapter(controller).registry
        if entry.role is DeviceRole.BUTTON_PAD
    )
    assert button_pad.source_mode is DeviceSource.EMULATED
    assert button_pad.status.value == "active"


def test_disabled_role_is_absent_but_semantic_controller_commands_still_apply() -> None:
    controller = build_test_engine(button_pad_source=DeviceSource.DISABLED)

    controller.execute(SetMaximumAssistance(True))

    assert application(controller).maximum_assistance_active is True
    assert application(controller).button_led_colours == MAXIMUM_LEDS
    button_pad = next(
        entry
        for entry in adapter(controller).registry
        if entry.role is DeviceRole.BUTTON_PAD
    )
    assert button_pad.status.value == "disabled"


def test_reset_releases_old_session_topology_devices_and_endpoints() -> None:
    controller = build_test_engine()
    old_topology = weakref.ref(controller.topology)
    old_vehicle = weakref.ref(controller.vehicle)
    assert controller.neotrellis is not None
    old_emulator = weakref.ref(controller.neotrellis)
    old_pi_buses = tuple(weakref.ref(bus) for bus in controller.pi_buses.values())

    controller.execute(ResetSimulation())
    gc.collect()

    assert adapter(controller).simulation_session_id == 2
    assert old_topology() is None
    assert old_vehicle() is None
    assert old_emulator() is None
    assert all(reference() is None for reference in old_pi_buses)


def test_first_startup_command_failure_has_honest_nonfatal_adapter_snapshot() -> None:
    engine = build_test_engine(servotronic_factory=RejectingServotronicPeer)

    current_diagnostics = diagnostics(engine)
    steering = adapter(engine).servotronic
    assert steering is not None
    assert current_diagnostics.health.fatal is False
    assert current_diagnostics.health.steering_actuator_fault is not None
    assert steering.effective_assistance == 0.0
    assert steering.last_command_reason is None
    assert engine.servotronic.attempts == 1


def test_pressing_button_creates_button_event_frame() -> None:
    controller = build_test_engine()

    result = controller.execute(PressButton(0))
    trace = controller.topology.trace()

    assert result.events[0]["source"] == "button-pad-emulator"
    assert trace[0].source == "button-pad-emulator"
    assert trace[0].frame.arbitration_id == 0x700
    assert trace[0].frame.data == b"\x00\x01"
    assert trace[0].network is CanNetwork.KCAN
    assert trace[0].sequence == 1


def test_tapping_button_emits_ordered_press_and_release_frames() -> None:
    controller = build_test_engine()

    controller.execute(TapButton(0))

    button_frames = [
        entry.frame.data
        for entry in controller.topology.trace()
        if entry.frame.arbitration_id == 0x700
    ]
    assert button_frames == [b"\x00\x01", b"\x00\x00"]
    assert application(controller).steering_mode is SteeringMode.MANUAL


def test_pressing_mode_button_selects_manual_and_causes_amber_led_snapshot() -> None:
    controller = build_test_engine()

    controller.execute(PressButton(0))
    trace = controller.topology.trace()

    assert trace[1].source == "pi"
    assert trace[1].frame.arbitration_id == 0x701
    assert trace[1].frame.data == b"\x04\x00\x00\x00\x00\x00\x00\x00"
    assert application(controller).steering_mode is SteeringMode.MANUAL
    assert application(controller).button_led_colours == (
        LedColour.AMBER,
    ) + (LedColour.OFF,) * 15


def test_releasing_button_preserves_authoritative_mode_led() -> None:
    controller = build_test_engine()
    controller.execute(PressButton(0))

    controller.execute(ReleaseButton(0))

    assert controller.topology.trace()[-1].frame.data == b"\x00\x00"
    assert application(controller).steering_mode is SteeringMode.MANUAL
    assert application(controller).button_led_colours == (
        LedColour.AMBER,
    ) + (LedColour.OFF,) * 15


def test_reset_clears_trace_and_restores_initial_application_state() -> None:
    controller = build_test_engine()
    controller.execute(PressButton(0))
    controller.execute(SetVehicleSpeed(42.5))
    controller.execute(SetEngineRpm(3500))
    controller.execute(SetOilTemperature(112.5))
    controller.execute(SetCoolantTemperature(98.0))
    controller.execute(ResetSimulation())
    current_application = application(controller)
    current_adapter = adapter(controller)

    assert current_application.steering_mode is SteeringMode.AUTO
    assert controller.vehicle.speed_kph is None
    assert controller.vehicle.rpm is None
    assert all(
        value.status is EngineTelemetryStatus.NEVER_OBSERVED and value.value is None
        for value in (
            current_application.engine.rpm,
            current_application.engine.oil_temperature_c,
            current_application.engine.coolant_temperature_c,
        )
    )
    assert (current_adapter.simulation_session_id, diagnostics(controller).revision) == (2, 1)
    assert current_application.button_led_colours == AUTO_LEDS
    assert controller.topology.trace() == ()

    inject_registry_frames(controller)
    controller.execute(PressButton(0))
    assert controller.topology.trace()[0].sequence == 1


def test_actuator_failure_is_nonfatal_and_reset_starts_with_healthy_adapter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = MutableClock()
    controllers: list[FailingServotronicPeer] = []

    def build_controller(
        watchdog_timeout_s: float,
        controller_clock: Callable[[], float],
    ) -> SimulatedServotronicPeer:
        controller = FailingServotronicPeer(watchdog_timeout_s, controller_clock)
        controllers.append(controller)
        return controller

    engine = build_test_engine(
        clock=clock,
        servotronic_factory=build_controller,
    )

    with caplog.at_level("ERROR"):
        failure_result = engine.execute(RunControlTimer(1.0))

    assert diagnostics(engine).health.fatal is False
    assert failure_result.events == ()
    assert engine.kernel.health.steering_actuator_fault is not None
    assert engine.kernel.health.steering_actuator_fault.message == ("actuator failed on attempt 2")
    assert controllers[0].attempts == 2
    assert "terminal shutdown effect failed and was discarded" not in caplog.text
    engine.execute(PressButton(0))

    engine.execute(ResetSimulation())

    assert adapter(engine).simulation_session_id == 2
    assert (diagnostics(engine).revision, diagnostics(engine).health.fatal) == (1, False)
    assert diagnostics(engine).revision == engine.kernel.diagnostics().revision


def test_reset_tolerates_nonfatal_shutdown_adapter_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    controllers: list[RejectingShutdownPeer] = []

    def build_controller(
        watchdog_timeout_s: float,
        clock: Callable[[], float],
    ) -> SimulatedServotronicPeer:
        controller = RejectingShutdownPeer(watchdog_timeout_s, clock)
        controllers.append(controller)
        return controller

    engine = build_test_engine(servotronic_factory=build_controller)

    with caplog.at_level("ERROR"):
        engine.execute(ResetSimulation())

    assert controllers[0].attempts == 2
    assert "fatal diagnostics" not in caplog.text
    assert adapter(engine).simulation_session_id == 2
    assert (diagnostics(engine).revision, diagnostics(engine).health.fatal) == (1, False)


def test_snapshot_exposes_default_node_membership_on_all_networks() -> None:
    current_adapter = adapter(build_test_engine())

    statuses = {status.network: status for status in current_adapter.networks}
    assert list(statuses) == [CanNetwork.KCAN, CanNetwork.PTCAN, CanNetwork.FCAN]
    assert statuses[CanNetwork.KCAN].nodes == (
        "pi",
        "simulated-vehicle",
        "button-pad-emulator",
        "servotronic-emulator",
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

    runtime = SimulatedControllerRuntime(config=replace(config, can_networks=networks))
    runtime.start()
    current_adapter = adapter(runtime)

    ptcan = next(
        status for status in current_adapter.networks if status.network is CanNetwork.PTCAN
    )
    assert ptcan.connected is False
    assert ptcan.nodes == ("simulated-vehicle",)


def test_invalid_button_index_raises() -> None:
    controller = build_test_engine()

    with pytest.raises(ValueError, match="button_index"):
        controller.execute(PressButton(LED_COUNT))


def test_assistance_and_maximum_buttons_run_through_the_simulated_can_slice() -> None:
    controller = build_test_engine()

    controller.execute(PressButton(2))
    assert application(controller).steering_mode is SteeringMode.MANUAL
    assert application(controller).manual_assistance_level == 0

    controller.execute(ReleaseButton(2))
    controller.execute(PressButton(2))
    assert application(controller).manual_assistance_level == 1

    controller.execute(ReleaseButton(2))
    controller.execute(PressButton(3))
    assert application(controller).maximum_assistance_active is True
    assert application(controller).manual_assistance_level == 7
    assert application(controller).button_led_colours[3] is LedColour.WHITE

    controller.execute(ReleaseButton(3))
    controller.execute(PressButton(3))
    assert application(controller).maximum_assistance_active is False
    assert application(controller).steering_mode is SteeringMode.MANUAL
    assert application(controller).manual_assistance_level == 1
    assert application(controller).button_led_colours[3] is LedColour.OFF


def test_assistance_button_cancels_maximum_override_through_can_slice() -> None:
    controller = build_test_engine()
    controller.execute(PressButton(2))
    controller.execute(ReleaseButton(2))
    controller.execute(PressButton(2))
    controller.execute(ReleaseButton(2))
    controller.execute(PressButton(3))
    controller.execute(ReleaseButton(3))

    controller.execute(PressButton(1))

    assert application(controller).steering_mode is SteeringMode.MANUAL
    assert application(controller).manual_assistance_level == 1
    assert application(controller).maximum_assistance_active is False
    assert application(controller).button_led_colours[3] is LedColour.OFF


def test_timer_updates_projection_when_it_recovers_a_timed_out_actuator() -> None:
    clock = MutableClock(10.0)
    controller = build_test_engine(clock=clock)

    clock.now = 11.5
    result = controller.execute(RunControlTimer(clock()))

    assert application(controller).speed_valid is False
    assert all(
        event["arbitration_id"]
        in {0x701, 0x703, 0x704, 0x706, 0x707}
        for event in result.events
    )
    assert adapter(controller).servotronic is not None
    assert adapter(controller).servotronic.watchdog_timed_out is False


def test_timer_updates_new_manual_actuator_projection() -> None:
    controller = build_test_engine()

    command = controller.execute(PressButton(0))
    timer = controller.execute(RunControlTimer(1.0))

    assert [event["type"] for event in command.events] == ["frame", "frame"]
    assert timer.events == ()
    assert adapter(controller).servotronic is not None
    assert adapter(controller).servotronic.last_command_reason == SteeringCommandReason.MANUAL.value


@pytest.mark.parametrize("value", [ButtonPressed(0), ApplicationState()])
def test_engine_rejects_domain_events_and_application_state(value: object) -> None:
    controller = build_test_engine()

    with pytest.raises(TypeError, match="unsupported simulation command"):
        controller.execute(value)  # type: ignore[arg-type]


def test_engine_clock_is_used_for_ingress_and_trace() -> None:
    clock = MutableClock(8.5)
    controller = build_test_engine(clock=clock)

    controller.execute(PressButton(0))

    assert {entry.monotonic_s for entry in controller.topology.trace()} == {8.5}


def test_high_beam_strobe_emits_all_pulses_to_virtual_vehicle_without_control_ticks() -> None:
    clock = MutableClock()
    config = replace(
        TEST_SIMULATOR_CONFIG,
        high_beam_strobe=HighBeamStrobeConfig(cycle_count=5),
    )
    controller = SimulatedControllerRuntime(config=config, clock=clock)
    controller.start()
    inject_registry_frames(controller)

    controller.execute(TapButton(4))
    for _ in range(10):
        assert controller.next_deadline() is not None
        clock.now = controller.next_deadline()
        controller.deadline(clock.now)

    high_beam_frames = [
        entry.frame
        for entry in controller.topology.trace()
        if entry.source == "pi"
        and entry.frame.arbitration_id == SIMULATION_ONLY_HIGH_BEAM_COMMAND_ID
    ]
    assert high_beam_frames == [
        CanFrame(SIMULATION_ONLY_HIGH_BEAM_COMMAND_ID, bytes((value,)), is_extended_id=True)
        for value in (1, 0) * 5
    ]
    assert controller.vehicle.high_beam_enabled is False
    assert application(controller).high_beam_strobe_active is False


def test_dropped_led_snapshot_is_not_replayed_and_next_snapshot_converges() -> None:
    clock = MutableClock()
    config = replace(
        simulator_config(),
        tx_policy=TxPolicyConfig(max_frames_per_network_window=1),
    )
    controller = SimulatedControllerRuntime(config=config, clock=clock)
    controller.start()
    inject_registry_frames(controller)
    clock.now = 1.0
    controller.topology.clear_trace()

    controller.execute(PressButton(0))
    accepted_application = application(controller)
    controller.execute(ReleaseButton(0))
    controller.execute(PressButton(0))
    dropped_application = application(controller)
    dropped_trace = controller.topology.trace()

    assert accepted_application.steering_mode is SteeringMode.MANUAL
    assert accepted_application.button_led_colours == MANUAL_LEDS
    assert dropped_application.steering_mode is SteeringMode.AUTO
    assert dropped_application.button_led_colours == AUTO_LEDS
    assert [entry.source for entry in dropped_trace].count("pi") == 1

    clock.now = 2.0
    before_next_decision_trace = controller.topology.trace()

    assert application(controller).button_led_colours == AUTO_LEDS
    assert [entry.source for entry in before_next_decision_trace].count("pi") == 1

    controller.execute(PressButton(3))
    converged_application = application(controller)
    converged_trace = controller.topology.trace()

    assert converged_application.maximum_assistance_active is True
    assert converged_application.button_led_colours == MAXIMUM_LEDS
    pi_frames = [entry.frame for entry in converged_trace if entry.source == "pi"]
    assert pi_frames == [
        CanFrame(0x701, b"\x04\x00\x00\x00\x00\x00\x00\x00"),
        CanFrame(0x701, b"\x04\x50\x00\x00\x00\x00\x00\x00"),
    ]


def test_simulated_speed_uses_can_decode_transition_and_actuator_path() -> None:
    clock = MutableClock(10.0)
    controller = build_test_engine(clock=clock)

    controller.execute(SetVehicleSpeed(15.0))
    speed = application(controller)
    speed_trace = controller.topology.trace()
    clock.now = 10.1
    controller.execute(RunControlTimer(clock()))
    controlled = adapter(controller)

    assert speed_trace[-1].source == "simulated-vehicle"
    assert speed_trace[-1].network is CanNetwork.FCAN
    assert speed.vehicle_speed_kph == 15.0
    assert controller.vehicle.speed_kph == 15.0
    assert controlled.servotronic is not None
    assert controlled.servotronic.effective_assistance == pytest.approx(
        5 / 6, abs=ASSISTANCE_QUANTIZATION_TOLERANCE
    )
    assert controlled.servotronic.last_command_reason == SteeringCommandReason.AUTO.value


def test_engine_signals_use_trace_decode_transition_and_canonical_snapshot_path() -> None:
    clock = MutableClock(10.0)
    controller = build_test_engine(clock=clock)

    controller.execute(SetEngineRpm(3500))
    controller.execute(SetOilTemperature(112.54))
    controller.execute(SetCoolantTemperature(98.0))
    current_application = application(controller)

    engine_frames = [
        entry
        for entry in controller.topology.trace()
        if entry.frame.arbitration_id
        in {
            SIMULATION_ONLY_ENGINE_RPM_ID,
            SIMULATION_ONLY_OIL_TEMPERATURE_ID,
            SIMULATION_ONLY_COOLANT_TEMPERATURE_ID,
        }
    ]
    assert [entry.network for entry in engine_frames] == [CanNetwork.PTCAN] * 3
    assert all(entry.source == "simulated-vehicle" for entry in engine_frames)
    assert current_application.engine.rpm.value == 3500
    assert current_application.engine.oil_temperature_c.value == 112.5
    assert current_application.engine.coolant_temperature_c.value == 98.0
    assert all(
        value.status is EngineTelemetryStatus.VALID
        for value in (
            current_application.engine.rpm,
            current_application.engine.oil_temperature_c,
            current_application.engine.coolant_temperature_c,
        )
    )


def test_timer_reemits_active_engine_signals_and_silence_ages_only_one() -> None:
    clock = MutableClock(1.0)
    controller = build_test_engine(clock=clock)
    controller.execute(SetEngineRpm(3500))
    controller.execute(SetOilTemperature(112.5))
    controller.execute(SetCoolantTemperature(98.0))
    controller.execute(SilenceOilTemperature())

    clock.now = 2.001
    controller.execute(RunControlTimer(clock()))
    current_application = application(controller)

    ids = [entry.frame.arbitration_id for entry in controller.topology.trace()]
    assert ids.count(SIMULATION_ONLY_ENGINE_RPM_ID) == 2
    assert ids.count(SIMULATION_ONLY_OIL_TEMPERATURE_ID) == 1
    assert ids.count(SIMULATION_ONLY_COOLANT_TEMPERATURE_ID) == 2
    assert current_application.engine.rpm.status is EngineTelemetryStatus.VALID
    assert current_application.engine.oil_temperature_c == EngineTelemetryValue(
        None,
        EngineTelemetryStatus.STALE,
    )
    assert current_application.engine.coolant_temperature_c.status is EngineTelemetryStatus.VALID


def test_selected_speed_is_refreshed_before_each_control_timer() -> None:
    clock = MutableClock(1.0)
    controller = build_test_engine(clock=clock)
    controller.execute(SetVehicleSpeed(30.0))

    clock.now = 2.001
    controller.execute(RunControlTimer(clock()))
    first = application(controller)
    clock.now = 3.5
    controller.execute(RunControlTimer(clock()))
    second_application = application(controller)
    second_adapter = adapter(controller)

    assert [entry.source for entry in controller.topology.trace()].count(
        "simulated-vehicle"
    ) == 3
    assert first.speed_valid is True
    assert second_application.speed_valid is True
    assert second_adapter.servotronic is not None
    assert second_adapter.servotronic.effective_assistance == pytest.approx(
        2 / 3, abs=ASSISTANCE_QUANTIZATION_TOLERANCE
    )
    assert second_adapter.servotronic.last_command_reason == SteeringCommandReason.AUTO.value


def test_speed_silence_becomes_stale_and_setting_speed_recovers_auto() -> None:
    clock = MutableClock(1.0)
    controller = build_test_engine(clock=clock)
    controller.execute(SetVehicleSpeed(30.0))
    controller.execute(SilenceVehicleSpeed())

    clock.now = 2.001
    controller.execute(RunControlTimer(clock()))
    stale_application = application(controller)
    stale_adapter = adapter(controller)
    controller.execute(SetVehicleSpeed(30.0))
    controller.execute(RunControlTimer(clock()))
    recovered_application = application(controller)
    recovered_adapter = adapter(controller)

    assert stale_application.speed_valid is False
    assert stale_adapter.servotronic is not None
    assert stale_adapter.servotronic.effective_assistance == 0.0
    assert stale_adapter.servotronic.last_command_reason == SteeringCommandReason.SPEED_STALE.value
    assert recovered_application.speed_valid is True
    assert recovered_adapter.servotronic is not None
    assert recovered_adapter.servotronic.effective_assistance == pytest.approx(
        2 / 3, abs=ASSISTANCE_QUANTIZATION_TOLERANCE
    )
    assert recovered_adapter.servotronic.last_command_reason == SteeringCommandReason.AUTO.value


def test_manual_and_maximum_commands_remain_bounded_without_speed() -> None:
    controller = build_test_engine()
    controller.execute(PressButton(0))
    controller.execute(RunControlTimer(0.1))
    manual = adapter(controller).servotronic
    controller.execute(PressButton(3))
    controller.execute(RunControlTimer(0.2))
    maximum = adapter(controller).servotronic

    assert manual is not None
    assert maximum is not None
    assert manual.effective_assistance == 0.0
    assert manual.last_command_reason == SteeringCommandReason.MANUAL.value
    assert maximum.effective_assistance == 1.0
    assert maximum.last_command_reason == SteeringCommandReason.MAXIMUM.value


def test_actuator_watchdog_falls_back_when_coordinator_commands_stop() -> None:
    clock = MutableClock()
    controller = build_test_engine(clock=clock)
    controller.execute(PressButton(3))
    controller.execute(RunControlTimer(clock()))

    clock.now = controller.config.simulation.steering_watchdog_timeout_s + 0.001
    steering = adapter(controller).servotronic

    assert steering is not None
    assert steering.watchdog_timed_out is True
    assert steering.effective_assistance == 0.0
    assert steering.last_command_reason == SteeringCommandReason.MAXIMUM.value
