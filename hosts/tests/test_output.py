import logging
import struct

import pytest
from e87canbus.adapters.output import (
    CanEffectFailure,
    EffectExecutor,
    EffectRequest,
    SafeCanTransmitter,
    SteeringActuatorFailure,
)
from e87canbus.config import CanNetwork, TxPolicyConfig
from e87canbus.domain.events import (
    ConfigureServotronicCurve,
    SetSteeringAssistance,
    SteeringCommandReason,
)
from e87canbus.domain.steering.curves import initial_active_steering_curve
from e87canbus.protocol.can import CanFrame
from e87canbus.protocol.servotronic_protocol import CurveResult, CurveSource, ServotronicStatus
from e87canbus.runners.simulation.bus import InMemoryCanTopology
from e87canbus.transport.isotp import IsoTpEndpoint


class FakeTransmitter:
    def __init__(self) -> None:
        self.sent: list[CanFrame] = []

    def send(self, frame: CanFrame) -> None:
        self.sent.append(frame)


class MutableClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class FakeSteeringActuator:
    def __init__(self) -> None:
        self.commands: list[SetSteeringAssistance] = []

    def set_assistance(self, command: SetSteeringAssistance) -> None:
        self.commands.append(command)


class FailingSteeringActuator:
    def set_assistance(self, command: SetSteeringAssistance) -> None:
        raise OSError(f"failed {command.assistance}")


class FailingTransmitter:
    def send(self, frame: CanFrame) -> None:
        raise OSError(f"failed {frame.arbitration_id}")


def test_servotronic_curve_effect_and_status_share_the_kcan_isotp_path() -> None:
    topology = InMemoryCanTopology(clock=lambda: 0.0)
    coordinator_bus = topology.create_bus(CanNetwork.KCAN, "coordinator")
    device_bus = topology.create_bus(CanNetwork.KCAN, "servotronic")
    executor = EffectExecutor(
        {CanNetwork.KCAN: SafeCanTransmitter(coordinator_bus, TxPolicyConfig())}
    )
    device = IsoTpEndpoint(
        tx_id=0x70B,
        rx_id=0x70A,
        send_frame=device_bus.send,
    )

    def pump() -> None:
        for _ in range(64):
            executor.poll_transport()
            device.poll()
            progressed = False
            while (frame := device_bus.receive(0)) is not None:
                assert frame.arbitration_id == 0x70A
                device.on_frame(frame)
                progressed = True
            while (frame := coordinator_bus.receive(0)) is not None:
                executor.on_frame(CanNetwork.KCAN, frame)
                progressed = True
            if not progressed and not device.transmitting:
                return
        raise AssertionError("Servotronic ISO-TP exchange did not settle")

    active = initial_active_steering_curve()
    effect = ConfigureServotronicCurve(active.definition, active.activation_revision)
    control = SetSteeringAssistance(0.75, SteeringCommandReason.MANUAL)
    assert executor.execute((EffectRequest(effect), EffectRequest(control))) == ()
    pump()
    request = device.receive_payload()
    assert request is not None and len(request) == 44
    unpacked = struct.unpack("<BBBBI8H8HI", request)
    assert unpacked[4] == active.activation_revision
    assert unpacked[5:13] == tuple(point.speed_deci_kph for point in active.definition.points)
    assert unpacked[13:21] == tuple(
        point.assistance_per_mille for point in active.definition.points
    )
    assert device.receive_payload() == bytes((1, 3, 0xEE, 0x02, 1))

    status = ServotronicStatus(
        CurveResult.ACCEPTED,
        CurveSource.COORDINATOR_RAM,
        active.activation_revision,
        int.from_bytes(request[-4:], "little"),
        425,
        700,
        90,
        True,
        0,
    )
    device.send(
        struct.pack(
            "<BBBBIIHHBBB",
            1,
            2,
            status.result,
            status.source,
            status.activation_revision,
            status.curve_crc32,
            status.speed_deci_kph,
            status.assistance_per_mille,
            status.pwm_duty,
            int(status.speed_fresh),
            status.inhibit_reason,
        )
    )
    pump()
    assert executor.take_servotronic_statuses() == (status,)


def test_explicit_steering_capability_receives_dimensionless_effect() -> None:
    actuator = FakeSteeringActuator()
    command = SetSteeringAssistance(0.5, SteeringCommandReason.MANUAL)

    EffectExecutor(steering_actuator=actuator).execute((EffectRequest(command),))

    assert actuator.commands == [command]


def test_can_and_steering_failures_are_explicit_distinct_values() -> None:
    from e87canbus.adapters.output import SendRegistryFrame
    from e87canbus.protocol.can import RoutedCanFrame

    command = SetSteeringAssistance(0.5, SteeringCommandReason.MANUAL)
    executor = EffectExecutor(
        {CanNetwork.KCAN: SafeCanTransmitter(FailingTransmitter(), TxPolicyConfig())},
        steering_actuator=FailingSteeringActuator(),
    )
    failures = executor.execute(
        (
            EffectRequest(
                SendRegistryFrame(RoutedCanFrame(CanNetwork.KCAN, CanFrame(0x706, b"\x10")))
            ),
            EffectRequest(command),
        )
    )
    assert failures == (
        CanEffectFailure(CanNetwork.KCAN, "failed 1798"),
        SteeringActuatorFailure("failed 0.5"),
    )


def test_effect_request_rejects_a_steering_reason_without_a_command() -> None:
    with pytest.raises(ValueError, match="executable effect"):
        EffectRequest(SteeringCommandReason.MANUAL)  # type: ignore[arg-type]


def test_alternating_payloads_on_one_id_share_network_window(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw = FakeTransmitter()
    policy = TxPolicyConfig(max_frames_per_network_window=2)
    transmitter = SafeCanTransmitter(raw, policy, MutableClock())
    frames = [CanFrame(0x708, bytes([value]) * 8) for value in range(3)]

    transmitter.send(frames[0])
    transmitter.send(frames[1])
    with caplog.at_level(logging.WARNING):
        transmitter.send(frames[2])

    assert raw.sent == frames[:2]
    assert "reason=network-window" in caplog.text


def test_dropped_frame_is_not_replayed_when_shared_network_window_refills(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = MutableClock()
    raw = FakeTransmitter()
    policy = TxPolicyConfig(max_frames_per_network_window=2)
    transmitter = SafeCanTransmitter(raw, policy, clock)
    frames = [CanFrame(0x100 + index, bytes([index])) for index in range(4)]

    transmitter.send(frames[0])
    clock.now = 0.2
    transmitter.send(frames[1])
    clock.now = 0.9
    with caplog.at_level(logging.WARNING):
        transmitter.send(frames[2])
    clock.now = 1.0
    transmitter.send(frames[3])

    assert raw.sent == [frames[0], frames[1], frames[3]]
    assert frames[2] not in raw.sent
    assert "reason=network-window" in caplog.text
