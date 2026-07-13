import logging

import pytest
from e87canbus.application.events import (
    LedColour,
    SetButtonLed,
    SetSteeringAssistance,
    SteeringCommandReason,
)
from e87canbus.config import CanNetwork, TxPolicyConfig
from e87canbus.output import (
    CanEffectFailure,
    EffectExecutor,
    SafeCanTransmitter,
    SteeringActuatorFailure,
)
from e87canbus.protocol.can import CanFrame


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


def test_default_executor_has_no_transmit_capability(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        EffectExecutor().execute((SetButtonLed(0, LedColour.BLUE),))

    assert "unavailable TX capability" in caplog.text


def test_explicit_transmit_capability_encodes_led_effect() -> None:
    raw = FakeTransmitter()
    executor = EffectExecutor(
        {CanNetwork.KCAN: SafeCanTransmitter(raw, TxPolicyConfig())}
    )

    executor.execute((SetButtonLed(0, LedColour.BLUE),))

    assert raw.sent == [CanFrame(0x701, b"\x00\x03")]


def test_explicit_steering_capability_receives_dimensionless_effect() -> None:
    actuator = FakeSteeringActuator()
    command = SetSteeringAssistance(0.5, SteeringCommandReason.MANUAL)

    EffectExecutor(steering_actuator=actuator).execute((command,))

    assert actuator.commands == [command]


def test_can_and_steering_failures_are_explicit_distinct_values() -> None:
    command = SetSteeringAssistance(0.5, SteeringCommandReason.MANUAL)
    executor = EffectExecutor(
        {
            CanNetwork.KCAN: SafeCanTransmitter(
                FailingTransmitter(),
                TxPolicyConfig(),
            )
        },
        steering_actuator=FailingSteeringActuator(),
    )

    failures = executor.execute((SetButtonLed(0, LedColour.BLUE), command))

    assert failures == (
        CanEffectFailure(CanNetwork.KCAN, "failed 1793"),
        SteeringActuatorFailure("failed 0.5"),
    )


def test_alternating_payloads_on_one_id_share_network_window(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw = FakeTransmitter()
    policy = TxPolicyConfig(max_frames_per_network_window=2)
    transmitter = SafeCanTransmitter(raw, policy, MutableClock())
    frames = [CanFrame(0x701, bytes([0, value])) for value in range(3)]

    transmitter.send(frames[0])
    transmitter.send(frames[1])
    with caplog.at_level(logging.WARNING):
        transmitter.send(frames[2])

    assert raw.sent == frames[:2]
    assert "reason=network-window" in caplog.text


def test_different_ids_share_network_window_and_refill_deterministically(
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
    assert "reason=network-window" in caplog.text
