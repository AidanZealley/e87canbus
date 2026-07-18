import logging

import pytest
from e87canbus.application.events import (
    BUTTON_LED_COUNT,
    SetSteeringAssistance,
    SteeringCommandReason,
)
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.can import (
    CanFrame,
    DeviceWelcomeAckPayload,
    decode_hello,
    encode_welcome_ack,
)
from e87canbus.protocol.generated import (
    BUTTON_PRESSED,
    BUTTON_RELEASED,
)
from e87canbus.simulation.bus import InMemoryCanNetwork, InMemoryCanTopology
from e87canbus.simulation.commands import SetVehicleSignal, SilenceVehicleSignal
from e87canbus.simulation.devices import (
    SimulatedNeoTrellisNode,
    SimulatedServotronicPeer,
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
from e87canbus.simulation.signals import VehicleSignal


class MutableClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def activate_neotrellis(
    node: SimulatedNeoTrellisNode,
    controller_bus,
    clock: MutableClock,
) -> None:
    assert node.advance(clock()) == 1
    hello_frame = controller_bus.receive(timeout_s=0)
    assert hello_frame is not None
    hello = decode_hello(hello_frame, node.ids.button_pad_hello)
    assert hello is not None
    controller_bus.send(
        encode_welcome_ack(
            DeviceWelcomeAckPayload(
                controller_protocol_version=1,
                response_code=0,
                device_id=hello.device_id,
                device_session_id=hello.device_session_id,
                controller_session_id=0x1234,
                device_sequence=hello.sequence,
            ),
            node.ids.button_pad_welcome_ack,
        )
    )
    node.process_pending(clock())
    assert node.advance(clock()) == 1


def test_neotrellis_sends_explicit_press_and_release_events() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    observer_bus = network.create_bus("observer")
    clock = MutableClock()
    node = SimulatedNeoTrellisNode(
        bus=network.create_bus("neotrellis"),
        ids=ids,
        clock=clock,
    )
    activate_neotrellis(node, observer_bus, clock)
    heartbeat = observer_bus.receive(timeout_s=0)
    assert heartbeat is not None

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

    with pytest.raises(ValueError, match=f"between 0 and {BUTTON_LED_COUNT - 1}"):
        node.send_button_event(BUTTON_LED_COUNT, pressed=True)


def test_connect_is_idempotent_while_peer_is_connected() -> None:
    network = InMemoryCanNetwork()
    node = SimulatedNeoTrellisNode(
        bus=network.create_bus("neotrellis"),
        ids=CustomCanIds(),
    )
    initial_session = node.session_id

    assert node.connect() is False

    assert node.session_id == initial_session


def test_neotrellis_rejects_buttons_without_fresh_operational_lease() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    controller_bus = network.create_bus("pi")
    clock = MutableClock()
    node = SimulatedNeoTrellisNode(
        bus=network.create_bus("neotrellis"),
        ids=ids,
        clock=clock,
    )
    assert node.send_button_event(0, pressed=True) is None

    activate_neotrellis(node, controller_bus, clock)
    assert controller_bus.receive(timeout_s=0) is not None
    clock.now = 3.1
    assert node.send_button_event(0, pressed=True) is None


def test_neotrellis_ignores_unknown_frame_id() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    clock = MutableClock()
    node = SimulatedNeoTrellisNode(
        bus=network.create_bus("neotrellis"),
        ids=ids,
        clock=clock,
    )
    activate_neotrellis(node, pi_bus, clock)
    assert pi_bus.receive(timeout_s=0) is not None

    pi_bus.send(CanFrame(0x123, b"\x00\x01"))



def test_simulated_vehicle_stores_and_emits_speed_as_an_external_fcan_frame() -> None:
    topology = InMemoryCanTopology()
    pi_bus = topology.create_bus(CanNetwork.FCAN, "pi")
    vehicle = SimulatedVehicleNode(
        {network: topology.create_bus(network, "simulated-vehicle") for network in CanNetwork}
    )

    vehicle.execute(SetVehicleSignal(VehicleSignal.SPEED, 42.5))
    frame = encode_simulated_speed(42.5)

    assert pi_bus.receive(timeout_s=0) == frame

    vehicle.emit()
    assert pi_bus.receive(timeout_s=0) == frame

    vehicle.execute(SilenceVehicleSignal(VehicleSignal.SPEED))
    vehicle.emit()
    assert pi_bus.receive(timeout_s=0) is None


def test_simulated_vehicle_engine_signals_emit_and_silence_independently_on_ptcan() -> None:
    topology = InMemoryCanTopology()
    pi_bus = topology.create_bus(CanNetwork.PTCAN, "pi")
    vehicle = SimulatedVehicleNode(
        {network: topology.create_bus(network, "simulated-vehicle") for network in CanNetwork}
    )

    vehicle.execute(SetVehicleSignal(VehicleSignal.RPM, 3500))
    vehicle.execute(SetVehicleSignal(VehicleSignal.OIL_TEMPERATURE, 112.54))
    vehicle.execute(SetVehicleSignal(VehicleSignal.COOLANT_TEMPERATURE, 98.0))
    assert [pi_bus.receive(timeout_s=0) for _ in range(3)] == [
        encode_simulated_engine_rpm(3500),
        encode_simulated_oil_temperature(112.5),
        encode_simulated_coolant_temperature(98.0),
    ]

    vehicle.execute(SilenceVehicleSignal(VehicleSignal.OIL_TEMPERATURE))
    vehicle.execute(SilenceVehicleSignal(VehicleSignal.OIL_TEMPERATURE))

    vehicle.emit()
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
    controller = SimulatedServotronicPeer(0.25, clock)
    command = SetSteeringAssistance(0.75, SteeringCommandReason.AUTO)

    controller.set_assistance(command)
    clock.now = 0.251

    assert controller.effective_assistance == 0.0
    assert controller.last_command_reason is SteeringCommandReason.AUTO
    assert controller.watchdog_timed_out is True
