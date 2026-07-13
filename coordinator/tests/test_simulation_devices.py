import logging

import pytest
from e87canbus.application.events import SetSteeringAssistance, SteeringCommandReason
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.can import (
    CanFrame,
    LedUpdatePayload,
    encode_led_update,
)
from e87canbus.protocol.generated import BUTTON_PRESSED, BUTTON_RELEASED, LED_COLOUR_GREEN
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


def test_neotrellis_led_update_changes_led_colours() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)

    pi_bus.send(
        encode_led_update(
            LedUpdatePayload(button_index=2, colour_code=LED_COLOUR_GREEN), ids
        )
    )

    updates = node.process_pending_led_updates()

    assert updates == [LedUpdatePayload(button_index=2, colour_code=LED_COLOUR_GREEN)]
    assert node.led_colours == {2: LED_COLOUR_GREEN}


def test_neotrellis_ignores_unknown_frame_id() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)

    pi_bus.send(CanFrame(0x123, b"\x00\x01"))

    assert node.process_pending_led_updates() == []
    assert node.led_colours == {}


def test_neotrellis_logs_and_ignores_malformed_led_update(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)

    pi_bus.send(CanFrame(ids.led_update, b"\x00"))

    with caplog.at_level(logging.WARNING):
        updates = node.process_pending_led_updates()

    assert updates == []
    assert node.led_colours == {}
    assert "sim neotrellis ignored malformed led update" in caplog.text


def test_simulated_vehicle_emits_speed_as_an_external_fcan_frame() -> None:
    topology = InMemoryCanTopology()
    pi_bus = topology.create_bus(CanNetwork.FCAN, "pi")
    vehicle = SimulatedVehicleNode(
        {
            network: topology.create_bus(network, "simulated-vehicle")
            for network in CanNetwork
        }
    )

    frame = vehicle.send_speed(42.5)

    assert frame == encode_simulated_speed(42.5)
    assert pi_bus.receive(timeout_s=0) == frame


def test_simulated_steering_watchdog_removes_assistance_after_silence() -> None:
    clock = MutableClock()
    controller = SimulatedSteeringController(0.25, clock)
    command = SetSteeringAssistance(0.75, SteeringCommandReason.AUTO)

    controller.set_assistance(command)
    clock.now = 0.251

    assert controller.assistance == 0.0
    assert controller.reason is SteeringCommandReason.AUTO
    assert controller.watchdog_timed_out is True
