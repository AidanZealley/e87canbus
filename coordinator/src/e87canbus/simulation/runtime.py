"""Single-owner simulation engine for the browser workbench."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any, assert_never

from e87canbus.adapters.can_io import CanReceiver
from e87canbus.adapters.output import (
    CanEffectFailure,
    EffectExecutor,
    EffectFailure,
    HighBeamActuatorFailure,
    SafeCanTransmitter,
    SteeringActuatorFailure,
)
from e87canbus.application.button_bindings import ButtonBindingProfile
from e87canbus.application.controller import ApplicationSnapshot
from e87canbus.application.events import (
    ButtonFeedbackDeadlineReached,
    HighBeamStrobeDeadlineReached,
)
from e87canbus.config import AppConfig, CanNetwork, CustomCanIds, simulator_config
from e87canbus.device import DeviceRole, DeviceSource
from e87canbus.features.steering import ActiveSteeringCurve
from e87canbus.kernel import (
    ActivateSteeringCurve,
    CanEffectExecutionFailed,
    Commit,
    ControllerInput,
    CoordinatorKernel,
    DeviceAdapterFailed,
    DiagnosticSnapshot,
    ExecuteOperatorIntent,
    InboxOverflowed,
    KernelStarted,
    ReceivedCanFrame,
    ShutdownRequested,
    StateTopic,
    SteeringActuatorFailed,
    TimerElapsed,
)
from e87canbus.service import (
    ControllerAdapterSnapshot,
    ControllerWorkUnavailable,
    ObservedLightingSnapshot,
    ObservedNetworkSnapshot,
    ObservedServotronicSnapshot,
    RuntimeExecution,
    RuntimeInputSink,
    SimulationDeviceUnavailable,
)
from e87canbus.simulation.bus import InMemoryCanTopology, SimulatedCanTraceEntry
from e87canbus.simulation.commands import (
    ConnectSimulatedDevice,
    DisconnectSimulatedDevice,
    PressButton,
    RebootSimulatedDevice,
    ReleaseButton,
    ResetSimulation,
    RunControlTimer,
    SetSimulatedDeviceProtocolVersion,
    SetSimulatedDeviceStatusCode,
    SetVehicleSignal,
    SilenceVehicleSignal,
    TapButton,
)
from e87canbus.simulation.devices import (
    SimulatedHighBeamActuator,
    SimulatedNeoTrellisNode,
    SimulatedRegistryPeer,
    SimulatedServotronicPeer,
    SimulatedVehicleNode,
)
from e87canbus.simulation.protocol import SimulationProtocolRouter
from e87canbus.simulation.vehicle_source import SyntheticVehicleSource

LOGGER = logging.getLogger(__name__)

MAX_VIRTUAL_DRAIN_ITERATIONS = 32
MAX_SIMULATION_BUS_FRAMES_PER_EXECUTION = 256
MAX_VIRTUAL_DEVICE_FRAMES_PER_EXECUTION = 128


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
        servotronic_factory: Callable[
            [float, Callable[[], float]], SimulatedServotronicPeer
        ] = SimulatedServotronicPeer,
        button_binding_profile: ButtonBindingProfile | None = None,
    ) -> None:
        self.config = config or simulator_config()
        if ids is not None:
            self.config = replace(self.config, custom_can_ids=ids)
        if button_pad_source is DeviceSource.PHYSICAL:
            raise ValueError("physical button pad cannot use the in-memory simulation runtime")
        self.button_pad_source = button_pad_source
        self._clock = clock
        self._servotronic_factory = servotronic_factory
        self._button_binding_profile = button_binding_profile
        self._session_id = 0
        self._started = False
        self._initial_steering_curve: ActiveSteeringCurve | None = None
        self._execution_commits: list[Commit] = []
        self._previous_projection: ControllerAdapterSnapshot | None = None
        self._previous_diagnostics: DiagnosticSnapshot | None = None
        self._frame_history = {network: [0, 0, 0, 0] for network in CanNetwork}
        self.topology: InMemoryCanTopology
        self.pi_buses: dict[CanNetwork, CanReceiver]
        self.neotrellis: SimulatedNeoTrellisNode | None
        self.servotronic: SimulatedServotronicPeer
        self.kernel: CoordinatorKernel
        self.executor: EffectExecutor

    def configure_initial_steering_curve(self, curve: ActiveSteeringCurve) -> None:
        if self._started:
            raise RuntimeError("initial steering curve must be configured before startup")
        self._initial_steering_curve = curve

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
        initial = False
        drain = True
        match command:
            case PressButton(index):
                self._send_button(index, pressed=True)
            case ReleaseButton(index):
                self._send_button(index, pressed=False)
            case TapButton(index):
                self._send_button(index, pressed=True)
                self._send_button(index, pressed=False)
            case RunControlTimer(now):
                self.vehicle.emit()
                self._drain_kernel_inputs()
                self._dispatch(TimerElapsed(now))
            case SetVehicleSignal() | SilenceVehicleSignal():
                self.vehicle.execute(command)
            case ReceivedCanFrame():
                self._dispatch(command)
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
                initial = True
                drain = False
            case ConnectSimulatedDevice(role):
                self._peer_for(role).connect()
            case DisconnectSimulatedDevice(role):
                self._peer_for(role).disconnect()
            case RebootSimulatedDevice(role):
                peer = self._peer_for(role)
                if not peer.connected:
                    raise SimulationDeviceUnavailable(role)
                peer.reboot()
            case SetSimulatedDeviceProtocolVersion(role, protocol_version):
                self._peer_for(role).set_protocol_version(protocol_version)
            case SetSimulatedDeviceStatusCode(role, status_code):
                self._peer_for(role).set_status_code(status_code)
            case ActivateSteeringCurve() | ExecuteOperatorIntent():
                self._dispatch(command)
            case InboxOverflowed() | DeviceAdapterFailed():
                self._dispatch(command)
                if self.kernel.health.fatal:
                    self._dispatch(ShutdownRequested(self._clock()))
            case _:
                raise TypeError(f"unsupported simulation command: {command!r}")

        if not drain:
            return self._complete((), initial=True)
        return self._process_pending(before_sequence, initial=initial)

    def timer(self, now: float) -> RuntimeExecution | None:
        if self.kernel.health.fatal:
            return None
        return self.execute(RunControlTimer(now))

    def next_deadline(self) -> float | None:
        deadlines = [
            deadline
            for deadline in (
                self.kernel.next_deadline(),
                *(peer.next_deadline for peer in self._virtual_peers()),
            )
            if deadline is not None
        ]
        return min(deadlines) if deadlines else None

    def deadline(self, now: float) -> RuntimeExecution | None:
        if self.kernel.health.fatal:
            return None
        self._require_started()
        self._execution_commits = []
        before_sequence = self.topology.latest_sequence
        if any(
            deadline is not None and deadline <= now
            for deadline in self.kernel.state.button_feedback_deadlines
        ):
            self._dispatch(ButtonFeedbackDeadlineReached(now))
        if (
            self.kernel.state.high_beam_next_transition_at is not None
            and self.kernel.state.high_beam_next_transition_at <= now
        ):
            self._dispatch(HighBeamStrobeDeadlineReached(now))
        if any(
            entry.next_deadline is not None and entry.next_deadline <= now
            for entry in self.kernel.registry
        ):
            self._dispatch(TimerElapsed(now))
        return self._process_pending(before_sequence, now=now)

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
            if item.tx_enabled:
                transmitters[item.network] = SafeCanTransmitter(
                    bus,
                    self.config.tx_policy,
                    self._clock,
                )
        vehicle_buses = {
            item.network: self.topology.create_bus(item.network, "simulated-vehicle")
            for item in self.config.can_networks
        }
        self.vehicle = SimulatedVehicleNode(
            vehicle_buses,
            SyntheticVehicleSource(self.config.simulation.synthetic_speed_network),
        )

        kcan_enabled = CanNetwork.KCAN in self.pi_buses

        self.neotrellis = (
            SimulatedNeoTrellisNode(
                bus=self.topology.create_bus(CanNetwork.KCAN, "button-pad-emulator"),
                ids=self.config.custom_can_ids,
                clock=self._clock,
            )
            if self.button_pad_source is DeviceSource.EMULATED and kcan_enabled
            else None
        )
        self.servotronic = self._servotronic_factory(
            self.config.simulation.steering_watchdog_timeout_s,
            self._clock,
        )
        if kcan_enabled:
            self.servotronic.configure_registry(
                self.topology.create_bus(CanNetwork.KCAN, "servotronic-emulator"),
                self.config.custom_can_ids,
            )

        router = SimulationProtocolRouter(
            self.config.custom_can_ids,
            button_input_enabled=self.button_pad_source is DeviceSource.EMULATED,
            synthetic_speed_network=self.config.simulation.synthetic_speed_network,
        )
        self.kernel = CoordinatorKernel(
            steering_config=self.config.steering,
            engine_telemetry_config=self.config.engine_telemetry,
            high_beam_strobe_config=self.config.high_beam_strobe,
            router=router,
            device_sources={
                DeviceRole.BUTTON_PAD: self.button_pad_source,
                DeviceRole.SERVOTRONIC_CONTROLLER: (
                    DeviceSource.EMULATED if kcan_enabled else DeviceSource.DISABLED
                ),
            },
            servotronic_output_available=kcan_enabled,
            active_steering_curve=self._initial_steering_curve,
            button_binding_profile=self._button_binding_profile,
        )
        self.executor = EffectExecutor(
            transmitters,
            router,
            steering_actuator=self.servotronic,
            high_beam_actuator=(
                None
                if (transmitter := transmitters.get(CanNetwork.KCAN)) is None
                else SimulatedHighBeamActuator(transmitter)
            ),
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
        *,
        initial: bool = False,
        now: float | None = None,
    ) -> RuntimeExecution:
        self._drain_virtual_devices(now=now)
        self._process_button_output()
        self.vehicle.drain_pending()

        return self._complete(
            tuple(
                trace_entry_to_event(entry, self._session_id)
                for entry in self.topology.trace()
                if entry.sequence > before_sequence
            ),
            initial=initial,
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
        if initial or (
            previous is not None
            and (
                previous.registry != projection.registry or previous.networks != projection.networks
            )
        ):
            changed_topics.add(StateTopic.DEVICES)
        # Effective assistance is nested in the steering live payload, rather than
        # the devices payload.  Its projection must therefore advance the steering
        # topic revision so a live client receives a new curve marker.
        if initial or (previous is not None and previous.servotronic != projection.servotronic):
            changed_topics.add(StateTopic.STEERING)
        self._previous_projection = projection
        self._previous_diagnostics = diagnostics
        commit_count = len(self._execution_commits)
        return RuntimeExecution(events, frozenset(changed_topics), commit_count)

    def _drain_kernel_inputs(self, *, limit: int | None = None) -> int:
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
                if limit is not None and processed > limit:
                    raise RuntimeError("simulated CAN processing frame bound exceeded")
                observed_at = self._clock()
                self.executor.on_frame(network, frame)
                self._dispatch(ReceivedCanFrame(network, frame, observed_at))
            if not found_frame:
                return processed

    def _drain_virtual_devices(self, *, now: float | None = None) -> None:
        processed_frames = 0
        processing_time = self._clock() if now is None else now
        for _ in range(MAX_VIRTUAL_DRAIN_ITERATIONS):
            progress = 0
            for peer in self._virtual_peers():
                progress += peer.advance(processing_time)
            remaining = MAX_SIMULATION_BUS_FRAMES_PER_EXECUTION - processed_frames
            if remaining < 1:
                raise RuntimeError("simulated CAN processing frame bound exceeded")
            kernel_frames = self._drain_kernel_inputs(limit=remaining)
            processed_frames += kernel_frames
            progress += kernel_frames
            for peer in self._virtual_peers():
                remaining = MAX_VIRTUAL_DEVICE_FRAMES_PER_EXECUTION - processed_frames
                if remaining < 1:
                    raise RuntimeError("simulated virtual-device frame bound exceeded")
                peer_frames = peer.process_pending(processing_time, limit=remaining)
                processed_frames += peer_frames
                progress += peer_frames
            if progress == 0:
                return
        raise RuntimeError("simulated virtual-device fixed-point bound exceeded")

    def _virtual_peers(self) -> tuple[SimulatedRegistryPeer, ...]:
        return tuple(
            peer
            for peer in (self.neotrellis, self.servotronic)
            if peer is not None and peer.bus is not None
        )

    def _peer_for(self, role: DeviceRole) -> SimulatedRegistryPeer:
        if not isinstance(role, DeviceRole):
            raise ValueError("simulation device role must be a supported DeviceRole")
        peer = {
            DeviceRole.BUTTON_PAD: self.neotrellis,
            DeviceRole.SERVOTRONIC_CONTROLLER: self.servotronic,
        }[role]
        if peer is None or peer.bus is None:
            raise SimulationDeviceUnavailable(role)
        return peer

    def _dispatch(self, kernel_input: ControllerInput) -> Commit | None:
        commit = self.kernel.dispatch(kernel_input)
        commits = [] if commit is None else [commit]
        failures = () if commit is None else self.executor.execute(commit.effects)
        for failure in failures:
            failure_commit = self.kernel.dispatch(_effect_failure_input(failure, self._clock()))
            if failure_commit is not None:
                commits.append(failure_commit)
                feedback_failures = self.executor.execute(failure_commit.effects)
                for feedback_failure in feedback_failures:
                    feedback_commit = self.kernel.dispatch(
                        _effect_failure_input(feedback_failure, self._clock())
                    )
                    if feedback_commit is not None:
                        commits.append(feedback_commit)
        if failures and self.kernel.health.fatal:
            shutdown = self.kernel.dispatch(ShutdownRequested(self._clock()))
            if shutdown is not None:
                commits.append(shutdown)
                # The terminal fallback is attempted once. A second actuator failure is not fed
                # back into the stopped kernel or retried, preserving the original fault.
                for terminal_failure in self.executor.execute(shutdown.effects):
                    LOGGER.error(
                        "simulation terminal shutdown effect failed and was discarded: %s",
                        terminal_failure,
                    )
        self._execution_commits.extend(commits)
        return commit

    def _adapter_projection(self) -> ControllerAdapterSnapshot:
        return ControllerAdapterSnapshot(
            simulation_session_id=self._session_id,
            registry=self.kernel.registry,
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
            servotronic=ObservedServotronicSnapshot(
                effective_assistance=self.servotronic.effective_assistance,
                last_command_reason=(
                    None
                    if self.servotronic.last_command_reason is None
                    else self.servotronic.last_command_reason.value
                ),
                watchdog_timed_out=self.servotronic.watchdog_timed_out,
            ),
            lighting=ObservedLightingSnapshot(
                high_beam_enabled=self.vehicle.high_beam_enabled,
            ),
        )

    def _process_button_output(self) -> None:
        emulator = self.neotrellis
        if emulator is None:
            return
        try:
            emulator.process_pending_led_programs()
        except (OSError, RuntimeError, ValueError) as exc:
            LOGGER.error("button-pad emulator failed: %s", exc)
            self._dispatch(DeviceAdapterFailed(DeviceRole.BUTTON_PAD, self._clock(), str(exc)))
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
        case CanEffectFailure(network, message, origin_button_index):
            return CanEffectExecutionFailed(network, failed_at, message, origin_button_index)
        case SteeringActuatorFailure(message, origin_button_index):
            return SteeringActuatorFailed(failed_at, message, origin_button_index)
        case HighBeamActuatorFailure(message, origin_button_index):
            return CanEffectExecutionFailed(
                CanNetwork.KCAN,
                failed_at,
                message,
                origin_button_index,
            )
        case _:
            assert_never(failure)
