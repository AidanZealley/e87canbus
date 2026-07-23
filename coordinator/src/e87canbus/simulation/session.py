"""Construction of one fresh simulation session's adapters, devices and kernel.

``build_session`` wires the in-memory CAN topology, virtual devices, kernel and
effect executor for a single simulation session and returns them as an immutable
bundle. The runtime owns the lifecycle (startup dispatch, resets); this only
builds the components so that wiring lives apart from the runtime's control flow.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from e87canbus.adapters.can_io import CanReceiver
from e87canbus.adapters.output import EffectExecutor, SafeCanTransmitter
from e87canbus.config import AppConfig, CanNetwork
from e87canbus.domain.button_bindings import ButtonBindingProfile
from e87canbus.domain.device import DeviceRole, DeviceSource
from e87canbus.domain.steering import ActiveSteeringCurve
from e87canbus.kernel import CoordinatorKernel
from e87canbus.simulation.bus import InMemoryCanTopology
from e87canbus.simulation.devices import (
    SimulatedHighBeamActuator,
    SimulatedNeoTrellisNode,
    SimulatedServotronicPeer,
    SimulatedVehicleNode,
)
from e87canbus.simulation.protocol import SimulationProtocolRouter
from e87canbus.simulation.vehicle_source import SyntheticVehicleSource


@dataclass(frozen=True)
class SimulationSession:
    """The components wired for one simulation session, before startup dispatch."""

    topology: InMemoryCanTopology
    pi_buses: dict[CanNetwork, CanReceiver]
    vehicle: SimulatedVehicleNode
    neotrellis: SimulatedNeoTrellisNode | None
    servotronic: SimulatedServotronicPeer
    kernel: CoordinatorKernel
    executor: EffectExecutor


def build_session(
    config: AppConfig,
    clock: Callable[[], float],
    *,
    button_pad_source: DeviceSource,
    servotronic_factory: Callable[[float, Callable[[], float]], SimulatedServotronicPeer],
    button_binding_profile: ButtonBindingProfile | None,
    initial_steering_curve: ActiveSteeringCurve | None,
) -> SimulationSession:
    topology = InMemoryCanTopology(
        trace_capacity=config.simulation.trace_capacity,
        clock=clock,
    )
    enabled = tuple(item for item in config.can_networks if item.enabled)

    pi_buses: dict[CanNetwork, CanReceiver] = {}
    transmitters: dict[CanNetwork, SafeCanTransmitter] = {}
    for item in enabled:
        bus = topology.create_bus(item.network, "pi")
        pi_buses[item.network] = bus
        if item.tx_enabled:
            transmitters[item.network] = SafeCanTransmitter(
                bus,
                config.tx_policy,
                clock,
            )
    vehicle_buses = {
        item.network: topology.create_bus(item.network, "simulated-vehicle")
        for item in config.can_networks
    }
    vehicle = SimulatedVehicleNode(
        vehicle_buses,
        SyntheticVehicleSource(config.simulation.synthetic_speed_network),
    )

    kcan_enabled = CanNetwork.KCAN in pi_buses

    neotrellis = (
        SimulatedNeoTrellisNode(
            bus=topology.create_bus(CanNetwork.KCAN, "button-pad-emulator"),
            ids=config.custom_can_ids,
            clock=clock,
        )
        if button_pad_source is DeviceSource.EMULATED and kcan_enabled
        else None
    )
    servotronic = servotronic_factory(
        config.simulation.steering_watchdog_timeout_s,
        clock,
    )
    if kcan_enabled:
        servotronic.configure_registry(
            topology.create_bus(CanNetwork.KCAN, "servotronic-emulator"),
            config.custom_can_ids,
        )

    router = SimulationProtocolRouter(
        config.custom_can_ids,
        button_input_enabled=button_pad_source is DeviceSource.EMULATED,
        synthetic_speed_network=config.simulation.synthetic_speed_network,
    )
    kernel = CoordinatorKernel(
        steering_config=config.steering,
        engine_telemetry_config=config.engine_telemetry,
        high_beam_strobe_config=config.high_beam_strobe,
        router=router,
        device_sources={
            DeviceRole.BUTTON_PAD: button_pad_source,
            DeviceRole.SERVOTRONIC_CONTROLLER: (
                DeviceSource.EMULATED if kcan_enabled else DeviceSource.DISABLED
            ),
        },
        servotronic_output_available=kcan_enabled,
        active_steering_curve=initial_steering_curve,
        button_binding_profile=button_binding_profile,
    )
    executor = EffectExecutor(
        transmitters,
        router,
        steering_actuator=servotronic,
        high_beam_actuator=(
            None
            if (transmitter := transmitters.get(CanNetwork.KCAN)) is None
            else SimulatedHighBeamActuator(transmitter)
        ),
    )
    return SimulationSession(
        topology=topology,
        pi_buses=pi_buses,
        vehicle=vehicle,
        neotrellis=neotrellis,
        servotronic=servotronic,
        kernel=kernel,
        executor=executor,
    )
