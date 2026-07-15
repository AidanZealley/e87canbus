"""Single-owner simulation engine for the browser workbench."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, assert_never

from e87canbus.application.controller import ApplicationSnapshot, button_led_state
from e87canbus.application.events import SteeringCommandReason
from e87canbus.can_io import CanReceiver
from e87canbus.config import AppConfig, CanNetwork, CanNetworkConfig, CustomCanIds, simulator_config
from e87canbus.device import DeviceProjection, DeviceRole, DeviceSource
from e87canbus.features.steering import CurveInterpolation
from e87canbus.output import (
    EMPTY_EFFECT_DIAGNOSTICS,
    CanEffectFailure,
    EffectExecutionDiagnostics,
    EffectExecutor,
    EffectFailure,
    SafeCanTransmitter,
    SteeringActuatorFailure,
    add_effect_diagnostics,
)
from e87canbus.protocol.router import LED_COLOUR_CODES
from e87canbus.runtime import (
    SUPPORTED_STEERING_CURVE_INTERPOLATIONS,
    ActivateSteeringCurve,
    CanEffectExecutionFailed,
    Commit,
    ControllerInput,
    CoordinatorKernel,
    DeviceAdapterFailed,
    InboxOverflowed,
    KernelStarted,
    ReceivedCanFrame,
    RuntimeFaultKind,
    SetMaximumAssistance,
    SetSteeringMode,
    ShutdownRequested,
    SteeringActuatorFailed,
    TimerElapsed,
)
from e87canbus.service import ControllerWorkUnavailable
from e87canbus.simulation.bus import InMemoryCanTopology, SimulatedCanTraceEntry
from e87canbus.simulation.devices import (
    SimulatedNeoTrellisNode,
    SimulatedSteeringController,
    SimulatedVehicleNode,
)
from e87canbus.simulation.protocol import SimulationProtocolRouter

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimulatedNetworkStatus:
    config: CanNetworkConfig
    connected: bool
    nodes: tuple[str, ...]


@dataclass(frozen=True)
class SimulatedSteeringSnapshot:
    effective_assistance: float
    last_command_reason: SteeringCommandReason | None
    watchdog_timed_out: bool


@dataclass(frozen=True)
class SimulatorSnapshot:
    session_id: int
    revision: int
    fatal: bool
    application: ApplicationSnapshot
    led_colours: tuple[int, ...]
    steering_controller: SimulatedSteeringSnapshot
    devices: tuple[DeviceProjection, ...]
    networks: tuple[SimulatedNetworkStatus, ...]


@dataclass(frozen=True)
class PressButton:
    index: int


@dataclass(frozen=True)
class ReleaseButton:
    index: int


@dataclass(frozen=True)
class RunControlTimer:
    now: float


@dataclass(frozen=True)
class SetVehicleSpeed:
    speed_kph: float


@dataclass(frozen=True)
class SilenceVehicleSpeed:
    pass


@dataclass(frozen=True)
class SetEngineRpm:
    rpm: int


@dataclass(frozen=True)
class SilenceEngineRpm:
    pass


@dataclass(frozen=True)
class SetOilTemperature:
    temperature_c: float


@dataclass(frozen=True)
class SilenceOilTemperature:
    pass


@dataclass(frozen=True)
class SetCoolantTemperature:
    temperature_c: float


@dataclass(frozen=True)
class SilenceCoolantTemperature:
    pass


@dataclass(frozen=True)
class ResetSimulation:
    pass


SimulationCommand = (
    PressButton
    | ReleaseButton
    | RunControlTimer
    | SetVehicleSpeed
    | SilenceVehicleSpeed
    | SetEngineRpm
    | SilenceEngineRpm
    | SetOilTemperature
    | SilenceOilTemperature
    | SetCoolantTemperature
    | SilenceCoolantTemperature
    | ResetSimulation
)

SemanticControllerCommand = (
    ActivateSteeringCurve | SetMaximumAssistance | SetSteeringMode
)

ControllerFailure = InboxOverflowed | DeviceAdapterFailed


@dataclass(frozen=True)
class SimulationResult:
    snapshot: SimulatorSnapshot
    events: tuple[dict[str, Any], ...]
    commits: tuple[Commit, ...] = ()


class SimulationSessionFailed(ControllerWorkUnavailable):
    """Raised when a normal command targets a terminal simulation session."""


SteeringControllerFactory = Callable[
    [float, Callable[[], float]],
    SimulatedSteeringController,
]
EffectFailureInput = CanEffectExecutionFailed | SteeringActuatorFailed


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


class SimulatedControllerRuntime:
    """Selected simulated adapters and devices; owned by ``ControllerService``."""

    def __init__(
        self,
        ids: CustomCanIds | None = None,
        *,
        config: AppConfig | None = None,
        button_pad_source: DeviceSource = DeviceSource.EMULATED,
        clock: Callable[[], float] = time.monotonic,
        steering_controller_factory: SteeringControllerFactory = SimulatedSteeringController,
        supported_steering_curve_interpolations: tuple[CurveInterpolation, ...] = (
            SUPPORTED_STEERING_CURVE_INTERPOLATIONS
        ),
    ) -> None:
        self.config = config or simulator_config()
        if ids is not None:
            self.config = replace(self.config, custom_can_ids=ids)
        if button_pad_source is DeviceSource.PHYSICAL:
            raise ValueError("physical button pad cannot use the in-memory simulation runtime")
        self.button_pad_source = button_pad_source
        self._clock = clock
        self._steering_controller_factory = steering_controller_factory
        self._supported_steering_curve_interpolations = supported_steering_curve_interpolations
        self._session_id = 0
        self._started = False
        self._execution_commits: list[Commit] = []
        self._effect_history = EMPTY_EFFECT_DIAGNOSTICS
        self.topology: InMemoryCanTopology
        self.pi_buses: dict[CanNetwork, CanReceiver]
        self.vehicle: SimulatedVehicleNode
        self.neotrellis: SimulatedNeoTrellisNode | None
        self.steering_controller: SimulatedSteeringController
        self.kernel: CoordinatorKernel
        self.executor: EffectExecutor

    def start(self) -> SimulationResult:
        if self._started:
            raise RuntimeError("simulated controller runtime may be started exactly once")
        self._started = True
        self._execution_commits = []
        self._build_session()
        snapshot = self.snapshot()
        return SimulationResult(snapshot, (), tuple(self._execution_commits))

    def snapshot(self) -> SimulatorSnapshot:
        self._require_started()
        diagnostics = self.kernel.diagnostics()
        return SimulatorSnapshot(
            session_id=self._session_id,
            revision=diagnostics.revision,
            fatal=diagnostics.health.fatal,
            application=self.kernel.snapshot(),
            led_colours=self._desired_led_colours(),
            steering_controller=self._steering_snapshot(),
            devices=self._device_projections(),
            networks=tuple(
                SimulatedNetworkStatus(
                    config=network_config,
                    connected=network_config.network in self.pi_buses,
                    nodes=self.topology.nodes(network_config.network),
                )
                for network_config in self.config.can_networks
            ),
        )

    def execute(self, command: SimulationCommand) -> SimulationResult:
        self._require_started()
        if self.kernel.health.fatal and not isinstance(command, ResetSimulation):
            raise SimulationSessionFailed(
                "simulation session has fatal kernel health; reset required"
            )

        self._execution_commits = []
        before_sequence = self.topology.latest_sequence
        match command:
            case PressButton(index):
                self._send_button(index, pressed=True)
            case ReleaseButton(index):
                self._send_button(index, pressed=False)
            case RunControlTimer(now):
                self.vehicle.emit_speed()
                self.vehicle.emit_engine_rpm()
                self.vehicle.emit_oil_temperature()
                self.vehicle.emit_coolant_temperature()
                self._drain_kernel_inputs()
                self._dispatch(TimerElapsed(now))
            case SetVehicleSpeed(speed_kph):
                self.vehicle.set_speed(speed_kph)
            case SilenceVehicleSpeed():
                self.vehicle.silence_speed()
            case SetEngineRpm(rpm):
                self.vehicle.set_engine_rpm(rpm)
            case SilenceEngineRpm():
                self.vehicle.silence_engine_rpm()
            case SetOilTemperature(temperature_c):
                self.vehicle.set_oil_temperature(temperature_c)
            case SilenceOilTemperature():
                self.vehicle.silence_oil_temperature()
            case SetCoolantTemperature(temperature_c):
                self.vehicle.set_coolant_temperature(temperature_c)
            case SilenceCoolantTemperature():
                self.vehicle.silence_coolant_temperature()
            case ResetSimulation():
                replaced_session_id = self._session_id
                self._dispatch(ShutdownRequested(self._clock()))
                if self.kernel.health.fatal:
                    LOGGER.error(
                        "reset replaced simulation session %d with fatal diagnostics; "
                        "the new session starts healthy",
                        replaced_session_id,
                    )
                self._build_session()
                before_sequence = 0
            case _:
                raise TypeError(f"unsupported simulation command: {command!r}")

        return self._process_pending(before_sequence)

    def execute_controller_command(
        self,
        command: SemanticControllerCommand,
    ) -> SimulationResult:
        """Run semantic controller intent through the same kernel/effect path."""

        self._require_started()
        if self.kernel.health.fatal:
            raise SimulationSessionFailed(
                "simulation session has fatal kernel health; reset required"
            )
        before_sequence = self.topology.latest_sequence
        self._execution_commits = []
        self._dispatch(command)
        return self._process_pending(before_sequence)

    def execute_controller_failure(self, failure: ControllerFailure) -> SimulationResult:
        """Record a service/adapter failure through the ordered kernel boundary."""

        self._require_started()
        before_sequence = self.topology.latest_sequence
        self._execution_commits = []
        self._dispatch(failure)
        if self.kernel.health.fatal:
            self._dispatch(ShutdownRequested(self._clock()))
        return self._process_pending(before_sequence)

    def shutdown(self) -> SimulationResult:
        self._require_started()
        self._execution_commits = []
        before_sequence = self.topology.latest_sequence
        self._dispatch(ShutdownRequested(self._clock()))
        return self._process_pending(before_sequence)

    def _build_session(self) -> None:
        if hasattr(self, "executor"):
            self._effect_history = add_effect_diagnostics(
                self._effect_history,
                self.executor.diagnostics,
            )
        self._session_id += 1
        self.topology = InMemoryCanTopology(
            trace_capacity=self.config.simulation.trace_capacity,
            clock=self._clock,
        )
        enabled = tuple(item for item in self.config.can_networks if item.enabled)

        self.pi_buses = {}
        transmitters: dict[CanNetwork, SafeCanTransmitter] = {}
        for item in enabled:
            bus = self.topology.create_bus(item.network, "pi")
            self.pi_buses[item.network] = bus
            if (
                item.tx_enabled
                and (
                    item.network is not CanNetwork.KCAN
                    or self.button_pad_source is DeviceSource.EMULATED
                )
            ):
                transmitters[item.network] = SafeCanTransmitter(
                    bus,
                    self.config.tx_policy,
                    self._clock,
                )
        vehicle_buses = {
            item.network: self.topology.create_bus(item.network, "simulated-vehicle")
            for item in self.config.can_networks
        }
        self.vehicle = SimulatedVehicleNode(vehicle_buses)

        self.neotrellis = (
            SimulatedNeoTrellisNode(
                bus=self.topology.create_bus(CanNetwork.KCAN, "button-pad-emulator"),
                ids=self.config.custom_can_ids,
                clock=self._clock,
            )
            if self.button_pad_source is DeviceSource.EMULATED
            else None
        )
        self.steering_controller = self._steering_controller_factory(
            self.config.simulation.steering_watchdog_timeout_s,
            self._clock,
        )

        router = SimulationProtocolRouter(
            self.config.custom_can_ids,
            button_input_enabled=self.button_pad_source is DeviceSource.EMULATED,
        )
        self.kernel = CoordinatorKernel(
            steering_config=self.config.steering,
            engine_telemetry_config=self.config.engine_telemetry,
            router=router,
            supported_steering_curve_interpolations=(self._supported_steering_curve_interpolations),
        )
        self.executor = EffectExecutor(
            transmitters,
            router,
            steering_actuator=self.steering_controller,
        )

        startup = self._dispatch(KernelStarted(self._clock()))
        if startup is None:
            raise RuntimeError("simulation kernel did not start")
        self._process_button_output()
        self.vehicle.drain_pending()
        self.topology.clear_trace()

    @property
    def effect_diagnostics(self) -> EffectExecutionDiagnostics:
        return add_effect_diagnostics(self._effect_history, self.executor.diagnostics)

    def _send_button(self, button_index: int, pressed: bool) -> None:
        neotrellis = self._require_emulated_button_pad()
        neotrellis.send_button_event(button_index, pressed)

    def _process_pending(
        self,
        before_sequence: int,
    ) -> SimulationResult:
        self._drain_kernel_inputs()
        self._process_button_output()
        self.vehicle.drain_pending()

        snapshot = self.snapshot()
        new_trace = tuple(
            entry for entry in self.topology.trace() if entry.sequence > before_sequence
        )
        events = [trace_entry_to_event(entry, self._session_id) for entry in new_trace]
        return SimulationResult(snapshot, tuple(events), tuple(self._execution_commits))

    def _drain_kernel_inputs(self) -> int:
        processed = 0
        ordered_networks = tuple(network for network in CanNetwork if network in self.pi_buses)
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

    def _dispatch(self, kernel_input: ControllerInput) -> Commit | None:
        commit = self.kernel.dispatch(kernel_input)
        if commit is None:
            return None
        self._execution_commits.append(commit)
        failures = self.executor.execute(commit.effects)
        if not failures:
            return commit

        for failure in failures:
            self.kernel.dispatch(_effect_failure_input(failure, self._clock()))
        shutdown = self.kernel.dispatch(ShutdownRequested(self._clock()))
        if shutdown is not None:
            self._execution_commits.append(shutdown)
            # The terminal fallback is attempted once. A second actuator failure is not fed
            # back into the stopped kernel or retried, preserving the original fault.
            for terminal_failure in self.executor.execute(shutdown.effects):
                LOGGER.error(
                    "simulation terminal shutdown effect failed and was discarded: %s",
                    terminal_failure,
                )
        return commit

    def _steering_snapshot(self) -> SimulatedSteeringSnapshot:
        return SimulatedSteeringSnapshot(
            effective_assistance=self.steering_controller.effective_assistance,
            last_command_reason=self.steering_controller.last_command_reason,
            watchdog_timed_out=self.steering_controller.watchdog_timed_out,
        )

    def _desired_led_colours(self) -> tuple[int, ...]:
        return tuple(
            LED_COLOUR_CODES[colour]
            for colour in button_led_state(self.kernel.state).colours
        )

    def _device_projections(self) -> tuple[DeviceProjection, ...]:
        if self.button_pad_source is DeviceSource.DISABLED:
            return ()
        emulator = self.neotrellis
        return (
            DeviceProjection(
                id=DeviceRole.BUTTON_PAD,
                label="Button pad",
                source_mode=self.button_pad_source,
                connected=True if emulator is not None else None,
                last_seen_monotonic_s=(
                    None if emulator is None else emulator.last_seen_monotonic_s
                ),
                desired_led_colours=self._desired_led_colours(),
                observed_led_colours=(
                    None if emulator is None else emulator.led_colours
                ),
                last_output_fault=self._button_output_fault(),
            ),
        )

    def _button_output_fault(self) -> str | None:
        network = next(
            item
            for item in self.kernel.health.networks
            if item.network is CanNetwork.KCAN
        )
        if (
            network.fault is None
            or network.fault.kind is not RuntimeFaultKind.CAN_EFFECT_EXECUTION
        ):
            return None
        return network.fault.message

    def _process_button_output(self) -> None:
        emulator = self.neotrellis
        if emulator is None:
            return
        try:
            emulator.process_pending_led_snapshots()
        except (OSError, RuntimeError, ValueError) as exc:
            LOGGER.error("button-pad emulator failed: %s", exc)
            self.kernel.dispatch(
                DeviceAdapterFailed(DeviceRole.BUTTON_PAD, self._clock(), str(exc))
            )
            self.neotrellis = None

    def _require_emulated_button_pad(self) -> SimulatedNeoTrellisNode:
        if self.neotrellis is None:
            raise ControllerWorkUnavailable(
                "button-pad emulator controls require the emulated source role"
            )
        return self.neotrellis

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("simulated controller runtime has not started")


def _effect_failure_input(
    failure: EffectFailure,
    failed_at: float,
) -> EffectFailureInput:
    match failure:
        case CanEffectFailure(network, message):
            return CanEffectExecutionFailed(network, failed_at, message)
        case SteeringActuatorFailure(message):
            return SteeringActuatorFailed(failed_at, message)
        case _:
            assert_never(failure)
