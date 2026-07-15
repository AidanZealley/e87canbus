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
    LED_COUNT,
)
from e87canbus.simulation.bus import InMemoryCanNetwork, InMemoryCanTopology
from e87canbus.simulation.devices import (
    SimulatedNeoTrellisNode,
    SimulatedSteeringController,
    SimulatedVehicleNode,
)
from e87canbus.simulation.protocol import (
    SIMULATION_ONLY_HIGH_BEAM_COMMAND_ID,
    encode_simulated_coolant_temperature,
    encode_simulated_engine_rpm,
    encode_simulated_high_beam_command,
    encode_simulated_oil_temperature,
    encode_simulated_speed,
)


class MutableClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_neotrellis_sends_explicit_press_and_release_events() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    observer_bus = network.create_bus("observer")
    node = SimulatedNeoTrellisNode(
        bus=network.create_bus("neotrellis"),
        ids=ids,
    )

    first = node.send_button_event(3, pressed=True)
    second = node.send_button_event(3, pressed=False)

    assert first == CanFrame(ids.button_event, bytes([3, BUTTON_PRESSED]))
    assert second == CanFrame(ids.button_event, bytes([3, BUTTON_RELEASED]))
    assert observer_bus.receive(timeout_s=0) == first
    assert observer_bus.receive(timeout_s=0) == second


def test_neotrellis_rejects_buttons_outside_generated_device_positions() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    node = SimulatedNeoTrellisNode(
        bus=network.create_bus("neotrellis"),
        ids=ids,
    )

    with pytest.raises(ValueError, match=f"between 0 and {LED_COUNT - 1}"):
        node.send_button_event(LED_COUNT, pressed=True)


def test_neotrellis_led_snapshot_replaces_all_colours() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)

    pi_bus.send(
        encode_led_snapshot(LedSnapshotPayload((LED_COLOUR_OFF, LED_COLOUR_GREEN) * 8), ids)
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
        {network: topology.create_bus(network, "simulated-vehicle") for network in CanNetwork}
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


def test_simulated_vehicle_engine_signals_emit_and_silence_independently_on_ptcan() -> None:
    topology = InMemoryCanTopology()
    pi_bus = topology.create_bus(CanNetwork.PTCAN, "pi")
    vehicle = SimulatedVehicleNode(
        {network: topology.create_bus(network, "simulated-vehicle") for network in CanNetwork}
    )

    assert vehicle.set_engine_rpm(3500) == encode_simulated_engine_rpm(3500)
    assert vehicle.set_oil_temperature(112.54) == encode_simulated_oil_temperature(112.54)
    assert vehicle.set_coolant_temperature(98.0) == encode_simulated_coolant_temperature(98.0)
    assert vehicle.oil_temperature_c == 112.5
    assert [pi_bus.receive(timeout_s=0) for _ in range(3)] == [
        encode_simulated_engine_rpm(3500),
        encode_simulated_oil_temperature(112.5),
        encode_simulated_coolant_temperature(98.0),
    ]

    vehicle.silence_oil_temperature()
    vehicle.silence_oil_temperature()

    assert vehicle.emit_engine_rpm() == encode_simulated_engine_rpm(3500)
    assert vehicle.emit_oil_temperature() is None
    assert vehicle.emit_coolant_temperature() == encode_simulated_coolant_temperature(98.0)
    assert [pi_bus.receive(timeout_s=0) for _ in range(2)] == [
        encode_simulated_engine_rpm(3500),
        encode_simulated_coolant_temperature(98.0),
    ]


def test_simulated_vehicle_consumes_private_pi_high_beam_command_on_kcan() -> None:
    topology = InMemoryCanTopology()
    pi_bus = topology.create_bus(CanNetwork.KCAN, "pi")
    vehicle = SimulatedVehicleNode(
        {network: topology.create_bus(network, "simulated-vehicle") for network in CanNetwork}
    )

    frame = encode_simulated_high_beam_command(True)
    pi_bus.send(frame)

    assert vehicle.drain_pending() == 1
    assert vehicle.high_beam_enabled is True
    assert topology.trace()[-1].source == "pi"
    assert topology.trace()[-1].network is CanNetwork.KCAN
    assert topology.trace()[-1].frame == frame


@pytest.mark.parametrize("data", [b"", b"\x02", b"\x01\x00"])
def test_simulated_vehicle_ignores_malformed_private_high_beam_command(
    data: bytes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    topology = InMemoryCanTopology()
    pi_bus = topology.create_bus(CanNetwork.KCAN, "pi")
    vehicle = SimulatedVehicleNode(
        {network: topology.create_bus(network, "simulated-vehicle") for network in CanNetwork},
        high_beam_enabled=True,
    )

    pi_bus.send(CanFrame(SIMULATION_ONLY_HIGH_BEAM_COMMAND_ID, data, is_extended_id=True))

    with caplog.at_level(logging.WARNING):
        assert vehicle.drain_pending() == 1

    assert vehicle.high_beam_enabled is True
    assert "simulated vehicle ignored malformed high-beam command" in caplog.text


def test_simulated_steering_watchdog_removes_assistance_after_silence() -> None:
    clock = MutableClock()
    controller = SimulatedSteeringController(0.25, clock)
    command = SetSteeringAssistance(0.75, SteeringCommandReason.AUTO)

    controller.set_assistance(command)
    clock.now = 0.251

    assert controller.effective_assistance == 0.0
    assert controller.last_command_reason is SteeringCommandReason.AUTO
    assert controller.watchdog_timed_out is True
