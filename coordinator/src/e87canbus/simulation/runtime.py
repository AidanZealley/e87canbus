"""Single-owner simulation engine for the browser workbench."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, assert_never

from e87canbus.application.controller import ApplicationSnapshot, button_led_state
from e87canbus.can_io import CanReceiver
from e87canbus.config import AppConfig, CanNetwork, CustomCanIds, simulator_config
from e87canbus.device import DeviceProjection, DeviceRole, DeviceSource
from e87canbus.features.steering import CurveInterpolation
from e87canbus.output import (
    EMPTY_EFFECT_DIAGNOSTICS,
    CanEffectFailure,
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
    DiagnosticSnapshot,
    InboxOverflowed,
    KernelStarted,
    ReceivedCanFrame,
    RuntimeFaultKind,
    SetMaximumAssistance,
    SetSteeringMode,
    ShutdownRequested,
    StateTopic,
    SteeringActuatorFailed,
    TimerElapsed,
)
from e87canbus.service import (
    ControllerAdapterSnapshot,
    ControllerWorkUnavailable,
    ObservedNetworkSnapshot,
    ObservedSteeringSnapshot,
    RuntimeExecution,
    RuntimeInputSink,
)
from e87canbus.simulation.bus import InMemoryCanTopology, SimulatedCanTraceEntry
from e87canbus.simulation.devices import (
    SimulatedNeoTrellisNode,
    SimulatedSteeringController,
    SimulatedVehicleNode,
)
from e87canbus.simulation.protocol import SimulationProtocolRouter

LOGGER = logging.getLogger(__name__)


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
        steering_controller_factory: Callable[
            [float, Callable[[], float]], SimulatedSteeringController
        ] = SimulatedSteeringController,
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
        self._previous_projection: ControllerAdapterSnapshot | None = None
        self._previous_diagnostics: DiagnosticSnapshot | None = None
        self._frame_history = {network: [0, 0, 0, 0] for network in CanNetwork}
        self.topology: InMemoryCanTopology
        self.pi_buses: dict[CanNetwork, CanReceiver]
        self.vehicle: SimulatedVehicleNode
        self.neotrellis: SimulatedNeoTrellisNode | None
        self.steering_controller: SimulatedSteeringController
        self.kernel: CoordinatorKernel
        self.executor: EffectExecutor

    def start(self, submit_input: RuntimeInputSink | None = None) -> RuntimeExecution:
        del submit_input
        if self._started:
            raise RuntimeError("simulated controller runtime may be started exactly once")
        self._started = True
        self._execution_commits = []
        self._build_session()
        return self._complete((), initial=True)

    def execute(self, command: object) -> RuntimeExecution:
        self._require_started()
        if self.kernel.health.fatal and not isinstance(command, ResetSimulation):
            raise ControllerWorkUnavailable(
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
            case ActivateSteeringCurve() | SetMaximumAssistance() | SetSteeringMode():
                self._dispatch(command)
            case InboxOverflowed() | DeviceAdapterFailed():
                self._dispatch(command)
                if self.kernel.health.fatal:
                    self._dispatch(ShutdownRequested(self._clock()))
            case _:
                raise TypeError(f"unsupported simulation command: {command!r}")

        return self._process_pending(before_sequence)

    def timer(self, now: float) -> RuntimeExecution | None:
        if self.kernel.health.fatal:
            return None
        return self.execute(RunControlTimer(now))

    def shutdown(self, now: float | None = None) -> RuntimeExecution:
        del now
        self._require_started()
        self._execution_commits = []
        before_sequence = self.topology.latest_sequence
        self._dispatch(ShutdownRequested(self._clock()))
        return self._process_pending(before_sequence)

    def close(self) -> None:
        """The in-process simulation runtime has no external endpoints to close."""

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

    def _send_button(self, button_index: int, pressed: bool) -> None:
        neotrellis = self._require_emulated_button_pad()
        neotrellis.send_button_event(button_index, pressed)

    def _process_pending(
        self,
        before_sequence: int,
    ) -> RuntimeExecution:
        self._drain_kernel_inputs()
        self._process_button_output()
        self.vehicle.drain_pending()

        return self._complete(
            tuple(
                trace_entry_to_event(entry, self._session_id)
                for entry in self.topology.trace()
                if entry.sequence > before_sequence
            )
        )

    def projection(
        self,
    ) -> tuple[ApplicationSnapshot, DiagnosticSnapshot, ControllerAdapterSnapshot]:
        diagnostics = self.kernel.diagnostics()
        health = diagnostics.health
        diagnostics = replace(
            diagnostics,
            health=replace(
                health,
                networks=tuple(
                    replace(
                        network,
                        received_frames=network.received_frames
                        + self._frame_history[network.network][0],
                        decoded_frames=network.decoded_frames
                        + self._frame_history[network.network][1],
                        ignored_frames=network.ignored_frames
                        + self._frame_history[network.network][2],
                        malformed_frames=network.malformed_frames
                        + self._frame_history[network.network][3],
                    )
                    for network in health.networks
                ),
            ),
        )
        return self.kernel.snapshot(), diagnostics, self._adapter_projection()

    @property
    def terminal(self) -> bool:
        # A fatal simulated session stays available for the explicit reset command.
        return False

    def _complete(
        self,
        events: tuple[dict[str, Any], ...],
        *,
        initial: bool = False,
    ) -> RuntimeExecution:
        changed_topics = {
            topic for commit in self._execution_commits for topic in commit.changed_topics
        }
        projection = self._adapter_projection()
        diagnostics = self.kernel.diagnostics()
        previous = self._previous_projection
        previous_diagnostics = self._previous_diagnostics
        if (
            previous is not None
            and previous.simulation_session_id != projection.simulation_session_id
            and previous_diagnostics is not None
        ):
            for network in previous_diagnostics.health.networks:
                history = self._frame_history[network.network]
                history[0] += network.received_frames
                history[1] += network.decoded_frames
                history[2] += network.ignored_frames
                history[3] += network.malformed_frames
        if initial:
            changed_topics.add(StateTopic.DEVICES)
        elif previous is not None:
            if (
                previous.devices != projection.devices
                or previous.networks != projection.networks
                or previous.steering != projection.steering
            ):
                changed_topics.add(StateTopic.DEVICES)
            if previous.led_colours != projection.led_colours:
                changed_topics.add(StateTopic.BUTTONS)
        self._previous_projection = projection
        self._previous_diagnostics = diagnostics
        if previous_diagnostics is not None and diagnostics.health != previous_diagnostics.health:
            changed_topics.add(StateTopic.HEALTH)
            if any(
                current.fault != prior.fault
                for current, prior in zip(
                    diagnostics.health.devices,
                    previous_diagnostics.health.devices,
                    strict=True,
                )
            ):
                changed_topics.add(StateTopic.DEVICES)
        commit_count = len(self._execution_commits)
        if commit_count == 0 and changed_topics:
            commit_count = 1
        return RuntimeExecution(events, frozenset(changed_topics), commit_count)

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

    def _adapter_projection(self) -> ControllerAdapterSnapshot:
        led_colours = tuple(
            LED_COLOUR_CODES[colour]
            for colour in button_led_state(self.kernel.state).colours
        )
        emulator = self.neotrellis
        kcan_fault = next(
            item.fault
            for item in self.kernel.health.networks
            if item.network is CanNetwork.KCAN
        )
        return ControllerAdapterSnapshot(
            simulation_session_id=self._session_id,
            led_colours=led_colours,
            devices=(
                ()
                if self.button_pad_source is DeviceSource.DISABLED
                else (
                    DeviceProjection(
                        id=DeviceRole.BUTTON_PAD,
                        label="Button pad",
                        source_mode=self.button_pad_source,
                        connected=True if emulator is not None else None,
                        last_seen_monotonic_s=(
                            None if emulator is None else emulator.last_seen_monotonic_s
                        ),
                        desired_led_colours=led_colours,
                        observed_led_colours=(
                            None if emulator is None else emulator.led_colours
                        ),
                        last_output_fault=(
                            kcan_fault.message
                            if kcan_fault is not None
                            and kcan_fault.kind is RuntimeFaultKind.CAN_EFFECT_EXECUTION
                            else None
                        ),
                    ),
                )
            ),
            networks=tuple(
                ObservedNetworkSnapshot(
                    network=item.network,
                    label=item.label,
                    interface=item.interface,
                    bitrate=item.bitrate,
                    connected=item.network in self.pi_buses,
                    nodes=self.topology.nodes(item.network),
                )
                for item in self.config.can_networks
            ),
            steering=ObservedSteeringSnapshot(
                effective_assistance=self.steering_controller.effective_assistance,
                last_command_reason=(
                    None
                    if self.steering_controller.last_command_reason is None
                    else self.steering_controller.last_command_reason.value
                ),
                watchdog_timed_out=self.steering_controller.watchdog_timed_out,
            ),
            effects=add_effect_diagnostics(
                self._effect_history,
                self.executor.diagnostics,
            ),
        )

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
