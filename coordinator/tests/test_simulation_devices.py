import logging

import pytest
from e87canbus.application.events import SetSteeringAssistance, SteeringCommandReason
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.can import (
    CanFrame,
    LedSnapshotPayload,
    encode_led_snapshot,
)
from e87canbus.protocol.generated import (
    BUTTON_PRESSED,
    BUTTON_RELEASED,
    LED_COLOUR_GREEN,
    LED_COLOUR_OFF,
)
from e87canbus.simulation.bus import InMemoryCanNetwork, InMemoryCanTopology
from e87canbus.simulation.devices import (
    SimulatedNeoTrellisNode,
    SimulatedSteeringController,
    SimulatedVehicleNode,
)
from e87canbus.simulation.protocol import encode_simulated_speed


class MutableClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_neotrellis_alternates_press_and_release_events() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    observer_bus = network.create_bus("observer")
    node = SimulatedNeoTrellisNode(
        bus=network.create_bus("neotrellis"),
        ids=ids,
        button_index=3,
    )

    first = node.send_next_button_event()
    second = node.send_next_button_event()

    assert first == CanFrame(ids.button_event, bytes([3, BUTTON_PRESSED]))
    assert second == CanFrame(ids.button_event, bytes([3, BUTTON_RELEASED]))
    assert observer_bus.receive(timeout_s=0) == first
    assert observer_bus.receive(timeout_s=0) == second


def test_neotrellis_led_snapshot_replaces_all_colours() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)

    pi_bus.send(
        encode_led_snapshot(
            LedSnapshotPayload((LED_COLOUR_OFF, LED_COLOUR_GREEN) * 8), ids
        )
    )

    snapshots = node.process_pending_led_snapshots()

    assert snapshots == [LedSnapshotPayload((LED_COLOUR_OFF, LED_COLOUR_GREEN) * 8)]
    assert node.led_colours == (LED_COLOUR_OFF, LED_COLOUR_GREEN) * 8


def test_neotrellis_ignores_unknown_frame_id() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)

    pi_bus.send(CanFrame(0x123, b"\x00\x01"))

    assert node.process_pending_led_snapshots() == []
    assert node.led_colours == (LED_COLOUR_OFF,) * 16


@pytest.mark.parametrize("data", [b"\x00" * 7, b"\x00" * 7 + b"\x60"])
def test_neotrellis_logs_and_atomically_ignores_malformed_led_snapshot(
    data: bytes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)

    prior = (LED_COLOUR_GREEN,) * 16
    pi_bus.send(encode_led_snapshot(LedSnapshotPayload(prior), ids))
    assert node.process_pending_led_snapshots() == [LedSnapshotPayload(prior)]
    pi_bus.send(CanFrame(ids.led_snapshot, data))

    with caplog.at_level(logging.WARNING):
        snapshots = node.process_pending_led_snapshots()

    assert snapshots == []
    assert node.led_colours == prior
    assert "sim neotrellis ignored malformed LED snapshot" in caplog.text


def test_simulated_vehicle_stores_and_emits_speed_as_an_external_fcan_frame() -> None:
    topology = InMemoryCanTopology()
    pi_bus = topology.create_bus(CanNetwork.FCAN, "pi")
    vehicle = SimulatedVehicleNode(
        {
            network: topology.create_bus(network, "simulated-vehicle")
            for network in CanNetwork
        }
    )

    frame = vehicle.set_speed(42.5)

    assert vehicle.speed_kph == 42.5
    assert frame == encode_simulated_speed(42.5)
    assert pi_bus.receive(timeout_s=0) == frame

    assert vehicle.emit_speed() == frame
    assert pi_bus.receive(timeout_s=0) == frame

    vehicle.silence_speed()
    assert vehicle.speed_kph is None
    assert vehicle.emit_speed() is None
    assert pi_bus.receive(timeout_s=0) is None


def test_simulated_steering_watchdog_removes_assistance_after_silence() -> None:
    clock = MutableClock()
    controller = SimulatedSteeringController(0.25, clock)
    command = SetSteeringAssistance(0.75, SteeringCommandReason.AUTO)

    controller.set_assistance(command)
    clock.now = 0.251

    assert controller.effective_assistance == 0.0
    assert controller.last_command_reason is SteeringCommandReason.AUTO
    assert controller.watchdog_timed_out is True
