"""Single-owner simulation engine for the browser workbench."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from e87canbus.application.controller import ApplicationSnapshot
from e87canbus.application.events import ControlTimerElapsed
from e87canbus.can_io import CanReceiver
from e87canbus.config import AppConfig, CanNetwork, CanNetworkConfig, CustomCanIds, simulator_config
from e87canbus.output import EffectExecutor, SafeCanTransmitter
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.runtime import (
    Commit,
    CoordinatorKernel,
    EffectExecutionFailed,
    KernelInput,
    KernelStarted,
    ReceivedCanFrame,
    ShutdownRequested,
)
from e87canbus.simulation.bus import InMemoryCanTopology, SimulatedCanTraceEntry
from e87canbus.simulation.devices import (
    SimulatedCar,
    SimulatedNeoTrellisNode,
    SimulatedSteeringControllerNode,
)

LOGGER = logging.getLogger(__name__)
MAX_CASCADE_PASSES = 32


@dataclass(frozen=True)
class SimulatedNetworkStatus:
    config: CanNetworkConfig
    connected: bool
    nodes: tuple[str, ...]


@dataclass(frozen=True)
class SimulatorSnapshot:
    session_id: int
    revision: int
    application: ApplicationSnapshot
    next_pressed: bool
    led_colours: dict[int, int]
    networks: tuple[SimulatedNetworkStatus, ...]
    trace: tuple[SimulatedCanTraceEntry, ...]


@dataclass(frozen=True)
class PressButton:
    index: int


@dataclass(frozen=True)
class ReleaseButton:
    index: int


@dataclass(frozen=True)
class StepButton:
    index: int


@dataclass(frozen=True)
class RunControlTimer:
    now: float


@dataclass(frozen=True)
class ResetSimulation:
    pass


SimulationCommand = PressButton | ReleaseButton | StepButton | RunControlTimer | ResetSimulation


@dataclass(frozen=True)
class SimulationResult:
    snapshot: SimulatorSnapshot
    events: tuple[dict[str, Any], ...]


def trace_entry_to_event(entry: SimulatedCanTraceEntry, session_id: int) -> dict[str, Any]:
    return {
        "type": "frame",
        "session_id": session_id,
        "sequence": entry.sequence,
        "network": entry.network.value,
        "source": entry.source,
        "arbitration_id": entry.frame.arbitration_id,
        "arbitration_id_hex": f"0x{entry.frame.arbitration_id:x}",
        "data_hex": entry.frame.data.hex(),
        "is_extended_id": entry.frame.is_extended_id,
        "monotonic_s": entry.monotonic_s,
    }


def network_status_to_dict(status: SimulatedNetworkStatus) -> dict[str, Any]:
    return {
        "id": status.config.network.value,
        "label": status.config.label,
        "interface": status.config.interface,
        "bitrate": status.config.bitrate,
        "connected": status.connected,
        "nodes": list(status.nodes),
    }


def snapshot_to_dict(
    snapshot: SimulatorSnapshot,
    *,
    include_trace: bool,
) -> dict[str, Any]:
    serialized: dict[str, Any] = {
        "session_id": snapshot.session_id,
        "revision": snapshot.revision,
        "application": {
            "vehicle_speed_kph": snapshot.application.vehicle_speed_kph,
            "speed_valid": snapshot.application.speed_valid,
            "steering_mode": snapshot.application.steering_mode.value,
            "manual_assistance_level": snapshot.application.manual_assistance_level,
            "maximum_assistance_active": snapshot.application.maximum_assistance_active,
        },
        "next_pressed": snapshot.next_pressed,
        "led_colours": snapshot.led_colours,
        "networks": [network_status_to_dict(status) for status in snapshot.networks],
    }
    if include_trace:
        serialized["trace"] = [
            trace_entry_to_event(entry, snapshot.session_id) for entry in snapshot.trace
        ]
    return serialized


def snapshot_event(snapshot: SimulatorSnapshot, *, include_trace: bool) -> dict[str, Any]:
    return {
        "type": "snapshot",
        "session_id": snapshot.session_id,
        "revision": snapshot.revision,
        "snapshot": snapshot_to_dict(snapshot, include_trace=include_trace),
    }


class SimulationEngine:
    def __init__(
        self,
        ids: CustomCanIds | None = None,
        button_count: int = 16,
        *,
        config: AppConfig | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if button_count < 1 or button_count > 256:
            raise ValueError("button_count must be between 1 and 256")
        self.config = config or simulator_config()
        if ids is not None:
            self.config = replace(self.config, custom_can_ids=ids)
        self.button_count = button_count
        self._clock = clock
        self._session_id = 0
        self._revision = 0
        self._build_session()

    def snapshot(self) -> SimulatorSnapshot:
        return SimulatorSnapshot(
            session_id=self._session_id,
            revision=self._revision,
            application=self.kernel.snapshot(),
            next_pressed=self.neotrellis.next_pressed,
            led_colours=dict(self.neotrellis.led_colours),
            networks=tuple(
                SimulatedNetworkStatus(
                    config=network_config,
                    connected=network_config.network in self.pi_buses,
                    nodes=self.topology.nodes(network_config.network),
                )
                for network_config in self.config.can_networks
            ),
            trace=self.topology.trace(),
        )

    def execute(self, command: SimulationCommand) -> SimulationResult:
        before_sequence = self.topology.latest_sequence
        before_application = self.kernel.snapshot()
        snapshot_trace: bool | None = False

        match command:
            case PressButton(index):
                self._send_button(index, pressed=True)
            case ReleaseButton(index):
                self._send_button(index, pressed=False)
            case StepButton(index):
                self._validate_button_index(index)
                self.neotrellis.button_index = index
                self.neotrellis.send_next_button_event()
            case RunControlTimer(now):
                self._dispatch(ControlTimerElapsed(now))
                snapshot_trace = None
            case ResetSimulation():
                self._dispatch(ShutdownRequested(self._clock()))
                self._build_session()
                before_sequence = 0
                snapshot_trace = True
            case _:
                raise TypeError(f"unsupported simulation command: {command!r}")

        result = self._process_pending(
            before_sequence,
            snapshot_trace=snapshot_trace,
        )
        if (
            isinstance(command, RunControlTimer)
            and result.snapshot.application != before_application
        ):
            return replace(
                result,
                events=(snapshot_event(result.snapshot, include_trace=False), *result.events),
            )
        return result

    def _build_session(self) -> None:
        self._session_id += 1
        self.topology = InMemoryCanTopology(
            trace_capacity=self.config.simulation.trace_capacity,
            clock=self._clock,
        )
        enabled = tuple(item for item in self.config.can_networks if item.enabled)

        self.pi_buses: dict[CanNetwork, CanReceiver] = {}
        transmitters: dict[CanNetwork, SafeCanTransmitter] = {}
        for item in enabled:
            bus = self.topology.create_bus(item.network, "pi")
            self.pi_buses[item.network] = bus
            if item.tx_enabled:
                transmitters[item.network] = SafeCanTransmitter(
                    bus,
                    self.config.tx_policy,
                    self._clock,
                )
        car_buses = {
            item.network: self.topology.create_bus(item.network, "simulated-car")
            for item in self.config.can_networks
        }
        self.car = SimulatedCar(car_buses)

        self.neotrellis = SimulatedNeoTrellisNode(
            bus=self.topology.create_bus(CanNetwork.KCAN, "neotrellis"),
            ids=self.config.custom_can_ids,
        )
        self.steering_controller = SimulatedSteeringControllerNode(
            bus=self.topology.create_bus(CanNetwork.KCAN, "steering-controller")
        )

        router = ProtocolRouter(self.config.custom_can_ids)
        self.kernel = CoordinatorKernel(
            steering_config=self.config.steering,
            router=router,
        )
        self.executor = EffectExecutor(transmitters, router)

        startup = self._dispatch(KernelStarted(self._clock()))
        if startup is None:
            raise RuntimeError("simulation kernel did not start")
        self.neotrellis.process_pending_led_updates()
        self.steering_controller.drain_pending()
        self.car.drain_pending()
        self.topology.clear_trace()

    def _send_button(self, button_index: int, pressed: bool) -> None:
        self._validate_button_index(button_index)
        self.neotrellis.send_button_event(button_index, pressed)
        self.neotrellis.next_pressed = not pressed

    def _process_pending(
        self,
        before_sequence: int,
        *,
        snapshot_trace: bool | None,
    ) -> SimulationResult:
        for _ in range(MAX_CASCADE_PASSES):
            processed = self._drain_kernel_inputs()
            processed += len(self.neotrellis.process_pending_led_updates())
            processed += self.steering_controller.drain_pending()
            processed += self.car.drain_pending()
            if processed == 0:
                break
        else:
            LOGGER.warning(
                "simulation did not quiesce after %d passes",
                MAX_CASCADE_PASSES,
            )

        snapshot = self.snapshot()
        new_trace = tuple(
            entry for entry in self.topology.trace() if entry.sequence > before_sequence
        )
        events: list[dict[str, Any]] = []
        if snapshot_trace is not None:
            events.append(snapshot_event(snapshot, include_trace=snapshot_trace))
        events.extend(trace_entry_to_event(entry, self._session_id) for entry in new_trace)
        return SimulationResult(snapshot, tuple(events))

    def _drain_kernel_inputs(self) -> int:
        processed = 0
        ordered_networks = tuple(
            network for network in CanNetwork if network in self.pi_buses
        )
        while True:
            found_frame = False
            for network in ordered_networks:
                frame = self.pi_buses[network].receive(timeout_s=0)
                if frame is None:
                    continue
                found_frame = True
                processed += 1
                observed_at = self._clock()
                self._dispatch(ReceivedCanFrame(network, frame, observed_at))
            if not found_frame:
                return processed

    def _dispatch(self, kernel_input: KernelInput) -> Commit | None:
        commit = self.kernel.dispatch(kernel_input)
        if commit is None:
            return None
        self._revision = commit.revision
        for failure in self.executor.execute(commit.effects):
            self.kernel.dispatch(
                EffectExecutionFailed(failure.network, self._clock(), failure.message)
            )
        return commit

    def _validate_button_index(self, button_index: int) -> None:
        if not 0 <= button_index < self.button_count:
            raise ValueError(f"button_index must be between 0 and {self.button_count - 1}")
