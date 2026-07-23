"""SocketCAN readers and the canonical live controller runtime adapter."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import assert_never

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.application.controller import ApplicationSnapshot
from e87canbus.application.events import (
    ButtonFeedbackDeadlineReached,
    HighBeamStrobeDeadlineReached,
)
from e87canbus.can_io import CanReceiver
from e87canbus.config import AppConfig, CanNetwork
from e87canbus.device import DeviceRole, DeviceSource
from e87canbus.features.steering import ActiveSteeringCurve
from e87canbus.kernel import (
    ActivateSteeringCurve,
    CanEffectExecutionFailed,
    CanReaderFailed,
    Commit,
    ControllerInput,
    CoordinatorKernel,
    DeviceAdapterFailed,
    DiagnosticSnapshot,
    ExecuteOperatorIntent,
    InboxOverflowed,
    KernelStarted,
    ReceivedCanFrame,
    ServotronicStatusObserved,
    ShutdownRequested,
    StateTopic,
    SteeringActuatorFailed,
    TimerElapsed,
)
from e87canbus.output import (
    CanEffectFailure,
    EffectExecutor,
    EffectFailure,
    HighBeamActuatorFailure,
    SafeCanTransmitter,
    SteeringActuatorFailure,
)
from e87canbus.protocol.can import RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.service import (
    ControllerAdapterSnapshot,
    ObservedNetworkSnapshot,
    RuntimeExecution,
    RuntimeInputSink,
    observed_servotronic_snapshot,
)
from e87canbus.simulation.commands import (
    SetVehicleSignal,
    SilenceVehicleSignal,
)
from e87canbus.simulation.protocol import SimulationProtocolRouter
from e87canbus.simulation.vehicle_source import SyntheticVehicleSource

LOGGER = logging.getLogger(__name__)

READER_JOIN_TIMEOUT_S = 1.0
MAX_CONSECUTIVE_READER_ERRORS = 3
INITIAL_READER_ERROR_BACKOFF_S = 0.05

ReaderInput = ReceivedCanFrame | CanReaderFailed
EffectFailureInput = CanEffectExecutionFailed | SteeringActuatorFailed
CONTROLLER_INPUT_TYPES = (
    KernelStarted,
    ReceivedCanFrame,
    TimerElapsed,
    ButtonFeedbackDeadlineReached,
    CanReaderFailed,
    CanEffectExecutionFailed,
    SteeringActuatorFailed,
    InboxOverflowed,
    DeviceAdapterFailed,
    ShutdownRequested,
    ActivateSteeringCurve,
    ExecuteOperatorIntent,
)
VEHICLE_COMMAND_TYPES = (
    SetVehicleSignal,
    SilenceVehicleSignal,
)


def read_frames_into_queue(
    network: CanNetwork,
    bus: CanReceiver,
    submit_input: RuntimeInputSink,
    capacity: int,
    stop: threading.Event,
    clock: Callable[[], float] = time.monotonic,
    receive_timeout_s: float = 0.2,
) -> None:
    """Read and timestamp one CAN interface until shutdown or repeated failure."""

    consecutive_errors = 0
    error_backoff_s = INITIAL_READER_ERROR_BACKOFF_S
    while not stop.is_set():
        try:
            frame = bus.receive(timeout_s=receive_timeout_s)
        except OSError as exc:
            consecutive_errors += 1
            if consecutive_errors >= MAX_CONSECUTIVE_READER_ERRORS:
                failed_at = clock()
                failed = CanReaderFailed(network, failed_at, str(exc))
                LOGGER.error(
                    "CAN reader failed; stopping: network=%s errors=%d error=%s",
                    network.value,
                    consecutive_errors,
                    exc,
                )
                _submit_or_stop(failed, submit_input, capacity, stop)
                return
            LOGGER.warning(
                "failed to receive CAN frame and continued: network=%s error=%s",
                network.value,
                exc,
            )
            stop.wait(error_backoff_s)
            error_backoff_s *= 2
            continue

        consecutive_errors = 0
        error_backoff_s = INITIAL_READER_ERROR_BACKOFF_S
        if frame is None:
            continue

        received_at = clock()
        _submit_or_stop(
            ReceivedCanFrame(network=network, frame=frame, received_at=received_at),
            submit_input,
            capacity,
            stop,
        )


def _submit_or_stop(
    kernel_input: ReaderInput,
    submit_input: RuntimeInputSink,
    capacity: int,
    stop: threading.Event,
) -> None:
    if not submit_input(kernel_input):
        LOGGER.error(
            "live CAN inbox overflow; stopping: network=%s capacity=%d",
            kernel_input.network.value,
            capacity,
        )
        stop.set()


def _execute(
    commit: Commit | None,
    executor: EffectExecutor,
    clock: Callable[[], float],
) -> tuple[EffectFailureInput, ...]:
    if commit is None:
        return ()
    return tuple(
        _effect_failure_input(failure, clock()) for failure in executor.execute(commit.effects)
    )


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
            # Live composition never grants this capability.  Retain a conservative
            # failure mapping should a future adapter violate that boundary.
            return CanEffectExecutionFailed(
                CanNetwork.KCAN,
                failed_at,
                message,
                origin_button_index,
            )
        case _:
            assert_never(failure)


class LiveControllerRuntime:
    """SocketCAN reader/effect adapter selected behind ``ControllerService``."""

    def __init__(
        self,
        config: AppConfig,
        *,
        button_pad_source: DeviceSource = DeviceSource.PHYSICAL,
        servotronic_source: DeviceSource | None = None,
        tx_grants: frozenset[CanNetwork] = frozenset(),
        bus_factory: Callable[[str], SocketCanBus] = SocketCanBus,
        synthetic_vehicle: SyntheticVehicleSource | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        configured_tx = frozenset(
            item.network for item in config.can_networks if item.enabled and item.tx_enabled
        )
        if not configured_tx.issubset(tx_grants):
            missing = ", ".join(sorted(network.value for network in configured_tx - tx_grants))
            raise ValueError(f"live CAN TX requires an explicit network grant: {missing}")
        self.config = config
        if button_pad_source is DeviceSource.EMULATED:
            raise ValueError("emulated button pad cannot use the live SocketCAN runtime")
        self._button_pad_source = button_pad_source
        selected_servotronic_source = servotronic_source or (
            DeviceSource.PHYSICAL
            if any(item.network is CanNetwork.KCAN and item.enabled for item in config.can_networks)
            else DeviceSource.DISABLED
        )
        if selected_servotronic_source is DeviceSource.EMULATED:
            raise ValueError("emulated Servotronic cannot use the SocketCAN runtime")
        self._servotronic_source = selected_servotronic_source
        self._tx_grants = tx_grants
        self._bus_factory = bus_factory
        self._synthetic_vehicle = synthetic_vehicle
        self._clock = clock
        router_type = SimulationProtocolRouter if synthetic_vehicle is not None else ProtocolRouter
        self._router = router_type(
            config.custom_can_ids,
            button_input_enabled=button_pad_source is DeviceSource.PHYSICAL,
            **(
                {"synthetic_speed_network": config.simulation.synthetic_speed_network}
                if synthetic_vehicle is not None
                else {}
            ),
        )
        servotronic_can_control_available = (
            selected_servotronic_source is DeviceSource.PHYSICAL
            and CanNetwork.KCAN in tx_grants
            and any(
                item.network is CanNetwork.KCAN and item.enabled and item.tx_enabled
                for item in config.can_networks
            )
        )
        self._kernel = CoordinatorKernel(
            steering_config=config.steering,
            engine_telemetry_config=config.engine_telemetry,
            high_beam_strobe_config=config.high_beam_strobe,
            router=self._router,
            device_sources={
                DeviceRole.BUTTON_PAD: button_pad_source,
                DeviceRole.SERVOTRONIC_CONTROLLER: selected_servotronic_source,
            },
            servotronic_output_available=servotronic_can_control_available,
            servotronic_config_available=servotronic_can_control_available,
        )
        self._executor = EffectExecutor(router=self._router)
        self._raw_buses: dict[CanNetwork, SocketCanBus] = {}
        self._transmitters: dict[CanNetwork, SafeCanTransmitter] = {}
        self._readers: list[threading.Thread] = []
        self._reader_stop = threading.Event()
        self._started = False

    def configure_initial_steering_curve(self, curve: ActiveSteeringCurve) -> None:
        if self._started:
            raise RuntimeError("initial steering curve must be configured before startup")
        self._kernel.configure_initial_steering_curve(curve)

    def start(self, submit_input: RuntimeInputSink) -> RuntimeExecution:
        if self._started:
            raise RuntimeError("live controller runtime may be started exactly once")
        self._started = True
        enabled = tuple(item for item in self.config.can_networks if item.enabled)
        try:
            for item in enabled:
                self._raw_buses[item.network] = self._bus_factory(item.interface)
        except OSError:
            self._close_buses()
            raise

        transmitters = {
            item.network: SafeCanTransmitter(
                self._raw_buses[item.network],
                self.config.tx_policy,
                self._clock,
            )
            for item in enabled
            if item.tx_enabled
            and item.network in self._tx_grants
            and (
                item.network is not CanNetwork.KCAN
                or self._button_pad_source is DeviceSource.PHYSICAL
                or self._servotronic_source is DeviceSource.PHYSICAL
            )
        }
        self._transmitters = transmitters
        self._executor = EffectExecutor(
            self._transmitters,
            self._router,
            button_pad_payload_interval_s=0.25,
        )
        execution = self._dispatch(KernelStarted(self._clock()))
        if execution is None:
            raise RuntimeError("live controller kernel did not start")
        execution = RuntimeExecution(
            execution.events,
            execution.changed_topics | {StateTopic.DEVICES},
            execution.commit_count,
        )

        self._readers = [
            threading.Thread(
                target=read_frames_into_queue,
                args=(
                    item.network,
                    self._raw_buses[item.network],
                    submit_input,
                    self.config.runtime_inbox_capacity,
                    self._reader_stop,
                ),
                daemon=True,
                name=f"{item.network.value}-reader",
            )
            for item in enabled
        ]
        for reader in self._readers:
            reader.start()
        return execution

    def execute(self, work: object) -> RuntimeExecution:
        if isinstance(work, VEHICLE_COMMAND_TYPES):
            if self._synthetic_vehicle is None:
                raise TypeError(f"unsupported live controller work: {work!r}")
            frames = self._synthetic_vehicle.execute(work)
            return self._dispatch_synthetic_frames(frames)
        if not isinstance(work, CONTROLLER_INPUT_TYPES):
            raise TypeError(f"unsupported live controller work: {work!r}")
        execution = self._dispatch(work)
        completed = execution or self._current_execution(None)
        return completed

    def timer(self, now: float) -> RuntimeExecution | None:
        executions: list[RuntimeExecution] = []
        if self._synthetic_vehicle is not None:
            emitted = self._dispatch_synthetic_frames(self._synthetic_vehicle.emit())
            if emitted.commit_count:
                executions.append(emitted)
        timer_execution = self._dispatch(TimerElapsed(now))
        if timer_execution is not None:
            executions.append(timer_execution)
        return _merge_executions(executions)

    def next_deadline(self) -> float | None:
        return self._kernel.next_deadline()

    def deadline(self, now: float) -> RuntimeExecution | None:
        executions: list[RuntimeExecution] = []
        if any(
            deadline is not None and deadline <= now
            for deadline in self._kernel.state.button_feedback_deadlines
        ):
            execution = self._dispatch(ButtonFeedbackDeadlineReached(now))
            if execution is not None:
                executions.append(execution)
        if (
            self._kernel.state.high_beam_next_transition_at is not None
            and self._kernel.state.high_beam_next_transition_at <= now
        ):
            execution = self._dispatch(HighBeamStrobeDeadlineReached(now))
            if execution is not None:
                executions.append(execution)
        if any(
            entry.next_deadline is not None and entry.next_deadline <= now
            for entry in self._kernel.registry
        ):
            execution = self._dispatch(TimerElapsed(now))
            if execution is not None:
                executions.append(execution)
        return _merge_executions(executions)

    def shutdown(self, now: float) -> RuntimeExecution | None:
        self._reader_stop.set()
        execution = self._dispatch(ShutdownRequested(now)) if self._started else None
        # Keep endpoints open through the ordered safe-state transition. Normal receivers use a
        # bounded timeout and stop before the publisher and adapters are closed by the lifecycle.
        for reader in self._readers:
            reader.join(timeout=READER_JOIN_TIMEOUT_S)
        alive = tuple(reader.name for reader in self._readers if reader.is_alive())
        if alive:
            names = ", ".join(alive)
            raise RuntimeError(f"live CAN readers did not stop before adapter close: {names}")
        return execution

    def close(self) -> None:
        self._close_buses()

    def projection(
        self,
    ) -> tuple[ApplicationSnapshot, DiagnosticSnapshot, ControllerAdapterSnapshot]:
        diagnostics = self._kernel.diagnostics()
        application = self._kernel.snapshot()
        enabled = tuple(item for item in self.config.can_networks if item.enabled)
        servotronic_status = self._kernel.servotronic_status
        return (
            application,
            diagnostics,
            ControllerAdapterSnapshot(
                simulation_session_id=None,
                registry=self._kernel.registry,
                networks=tuple(
                    ObservedNetworkSnapshot(
                        network=item.network,
                        label=item.label,
                        interface=item.interface,
                        bitrate=item.bitrate,
                        connected=item.network in self._raw_buses,
                        nodes=(),
                    )
                    for item in enabled
                ),
                servotronic=(
                    None
                    if servotronic_status is None
                    else observed_servotronic_snapshot(servotronic_status)
                ),
                lighting=None,
            ),
        )

    @property
    def terminal(self) -> bool:
        return self._kernel.health.fatal

    def _dispatch(self, work: ControllerInput) -> RuntimeExecution | None:
        if isinstance(work, ReceivedCanFrame):
            self._executor.on_frame(work.network, work.frame)
        commit = self._kernel.dispatch(work)
        commits = [] if commit is None else [commit]
        for status in self._executor.take_servotronic_statuses():
            status_commit = self._kernel.dispatch(ServotronicStatusObserved(status))
            if status_commit is not None:
                commits.append(status_commit)
        failures = _execute(commit, self._executor, self._clock)
        for failure in failures:
            failure_commit = self._kernel.dispatch(failure)
            if failure_commit is not None:
                commits.append(failure_commit)
                feedback_failures = _execute(failure_commit, self._executor, self._clock)
                for feedback_failure in feedback_failures:
                    feedback_commit = self._kernel.dispatch(feedback_failure)
                    if feedback_commit is not None:
                        commits.append(feedback_commit)
        self._executor.poll_transport()
        if not commits:
            return None
        return RuntimeExecution(
            changed_topics=frozenset(topic for item in commits for topic in item.changed_topics),
            commit_count=len(commits),
        )

    def _current_execution(self, commit: Commit | None) -> RuntimeExecution:
        return RuntimeExecution(
            changed_topics=(frozenset() if commit is None else commit.changed_topics),
            commit_count=0 if commit is None else 1,
        )

    def _dispatch_synthetic_frames(
        self,
        frames: tuple[RoutedCanFrame, ...],
    ) -> RuntimeExecution:
        executions: list[RuntimeExecution] = []
        for routed in frames:
            transmitter = self._transmitters.get(routed.network)
            if transmitter is not None:
                try:
                    transmitter.send(routed.frame)
                except OSError as exc:
                    failure = self._dispatch(
                        CanEffectExecutionFailed(
                            routed.network,
                            self._clock(),
                            str(exc),
                        )
                    )
                    if failure is not None:
                        executions.append(failure)
            execution = self._dispatch(
                ReceivedCanFrame(
                    network=routed.network,
                    frame=routed.frame,
                    received_at=self._clock(),
                )
            )
            if execution is not None:
                executions.append(execution)
        return _merge_executions(executions) or RuntimeExecution()

    def _close_buses(self) -> None:
        for network, bus in tuple(self._raw_buses.items()):
            try:
                bus.shutdown()
            except OSError as exc:
                LOGGER.error("failed to close SocketCAN network %s: %s", network.value, exc)
        self._raw_buses.clear()


def _merge_executions(executions: list[RuntimeExecution]) -> RuntimeExecution | None:
    if not executions:
        return None
    return RuntimeExecution(
        events=tuple(event for execution in executions for event in execution.events),
        changed_topics=frozenset(
            topic for execution in executions for topic in execution.changed_topics
        ),
        commit_count=sum(execution.commit_count for execution in executions),
    )
