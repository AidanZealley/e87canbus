import logging

import pytest
from e87canbus.application.events import (
    RGB_BLUE,
    RGB_OFF,
    RGB_WHITE,
    ButtonLedState,
    SetButtonPadProgram,
    SetButtonPadBreathe,
    SetHighBeam,
    SetSteeringAssistance,
    SteeringCommandReason,
    TriggerButtonPadBlink,
)
from e87canbus.button_pad import static_button_pad_program
from e87canbus.config import CanNetwork, TxPolicyConfig
from e87canbus.output import (
    CanEffectFailure,
    EffectExecutor,
    EffectRequest,
    SafeCanTransmitter,
    SteeringActuatorFailure,
)
from e87canbus.protocol.can import CanFrame

BLUE_LEDS = ButtonLedState((RGB_BLUE,) + (RGB_OFF,) * 15)
WHITE_LEDS = ButtonLedState((RGB_WHITE,) * 16)


def led_program(leds: ButtonLedState) -> SetButtonPadProgram:
    return SetButtonPadProgram(static_button_pad_program(leds.rgb))


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
        EffectExecutor().execute((EffectRequest(led_program(BLUE_LEDS)),))

    assert "unavailable TX capability" in caplog.text


def test_high_beam_requires_its_own_explicit_actuator_capability() -> None:
    """Network TX alone must not authorize the simulator-only high-beam command."""

    raw = FakeTransmitter()
    executor = EffectExecutor({CanNetwork.KCAN: SafeCanTransmitter(raw, TxPolicyConfig())})

    assert executor.execute((EffectRequest(SetHighBeam(True)),)) == ()
    assert raw.sent == []


def test_explicit_transmit_capability_encodes_led_effect() -> None:
    raw = FakeTransmitter()
    executor = EffectExecutor({CanNetwork.KCAN: SafeCanTransmitter(raw, TxPolicyConfig())})

    executor.execute((EffectRequest(led_program(BLUE_LEDS)),))

    # Two distinct tracks pack into one 32-byte transfer (First Frame length 0x020).
    assert raw.sent == [CanFrame(0x708, b"\x10\x20\x02\x01\x01\x00\x01\x00")]


def test_incremental_button_effects_are_single_frames_and_sequenced() -> None:
    raw = FakeTransmitter()
    executor = EffectExecutor({CanNetwork.KCAN: SafeCanTransmitter(raw, TxPolicyConfig())})

    executor.execute(
        (
            EffectRequest(TriggerButtonPadBlink(3)),
            EffectRequest(SetButtonPadBreathe(15, True)),
            EffectRequest(SetButtonPadBreathe(15, False)),
        )
    )

    assert raw.sent == [
        CanFrame(0x701, b"\x01\x01\x03\x00\x01\x00\x00\x00"),
        CanFrame(0x701, b"\x01\x02\x0f\x01\x01\x00\x00\x00"),
        CanFrame(0x701, b"\x01\x02\x0f\x02\x00\x00\x00\x00"),
    ]


def test_complete_led_snapshot_consumes_one_network_window_entry() -> None:
    raw = FakeTransmitter()
    executor = EffectExecutor(
        {
            CanNetwork.KCAN: SafeCanTransmitter(
                raw,
                TxPolicyConfig(max_frames_per_network_window=1),
                MutableClock(),
            )
        }
    )

    executor.execute(
        (
            EffectRequest(led_program(WHITE_LEDS)),
            EffectRequest(led_program(BLUE_LEDS)),
        )
    )

    assert raw.sent == [CanFrame(0x708, b"\x10\x10\x02\x81\xff\xff\x01\xff")]


def test_explicit_steering_capability_receives_dimensionless_effect() -> None:
    actuator = FakeSteeringActuator()
    command = SetSteeringAssistance(0.5, SteeringCommandReason.MANUAL)

    EffectExecutor(steering_actuator=actuator).execute((EffectRequest(command),))

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

    failures = executor.execute(
        (
            EffectRequest(led_program(BLUE_LEDS)),
            EffectRequest(command),
        )
    )

    assert failures == (
        CanEffectFailure(CanNetwork.KCAN, "failed 1800"),
        SteeringActuatorFailure("failed 0.5"),
    )


def test_executor_rejects_raw_effects_outside_effect_request_boundary() -> None:
    with pytest.raises(TypeError, match="EffectRequest"):
        EffectExecutor().execute((led_program(BLUE_LEDS),))  # type: ignore[arg-type]


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
