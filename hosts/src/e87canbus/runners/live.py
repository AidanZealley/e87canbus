"""SocketCAN readers and the canonical live controller runtime adapter."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from e87canbus.adapters.can_io import CanReceiver
from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.config import AppConfig, CanNetwork
from e87canbus.domain.buttons.profiles import ActiveButtonProfile
from e87canbus.domain.controller import ApplicationSnapshot
from e87canbus.domain.steering.curves import ActiveSteeringCurve
from e87canbus.kernel import (
    ActivateButtonProfile,
    ActivateSteeringCurve,
    CanReaderFailed,
    Commit,
    ControllerInput,
    CoordinatorKernel,
    DiagnosticSnapshot,
    ExecuteOperatorIntent,
    InboxOverflowed,
    KernelStarted,
    ReceivedCanFrame,
    ShutdownRequested,
    TimerElapsed,
)
from e87canbus.protocol.can import RoutedCanFrame
from e87canbus.runners.simulation.commands import (
    SetVehicleSignal,
    SetVehicleSweep,
    SilenceVehicleSignal,
)
from e87canbus.runners.simulation.protocol import SimulationProtocolRouter
from e87canbus.runners.simulation.vehicle_source import SyntheticVehicleSource
from e87canbus.service import (
    ControllerAdapterSnapshot,
    RuntimeExecution,
    RuntimeInputSink,
)

LOGGER = logging.getLogger(__name__)

READER_JOIN_TIMEOUT_S = 1.0
MAX_CONSECUTIVE_READER_ERRORS = 3
INITIAL_READER_ERROR_BACKOFF_S = 0.05

ReaderInput = ReceivedCanFrame | CanReaderFailed
CONTROLLER_INPUT_TYPES = (
    KernelStarted,
    ReceivedCanFrame,
    TimerElapsed,
    CanReaderFailed,
    InboxOverflowed,
    ShutdownRequested,
    ActivateButtonProfile,
    ActivateSteeringCurve,
    ExecuteOperatorIntent,
)
VEHICLE_COMMAND_TYPES = (
    SetVehicleSignal,
    SetVehicleSweep,
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


class LiveControllerRuntime:
    """SocketCAN receive adapter selected behind ``ControllerLoop``."""

    def __init__(
        self,
        config: AppConfig,
        *,
        bus_factory: Callable[[str], SocketCanBus] = SocketCanBus,
        synthetic_vehicle: SyntheticVehicleSource | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self._bus_factory = bus_factory
        self._synthetic_vehicle = synthetic_vehicle
        self._clock = clock
        decoder = (
            SimulationProtocolRouter(
                synthetic_speed_network=config.simulation.synthetic_speed_network
            ).decode
            if synthetic_vehicle is not None
            else None
        )
        self._kernel = CoordinatorKernel(
            steering_config=config.steering,
            engine_telemetry_config=config.engine_telemetry,
            decoder=decoder,
        )
        self._raw_buses: dict[CanNetwork, SocketCanBus] = {}
        self._readers: list[threading.Thread] = []
        self._reader_stop = threading.Event()
        self._started = False

    def configure_initial_steering_curve(self, curve: ActiveSteeringCurve) -> None:
        if self._started:
            raise RuntimeError("initial steering curve must be configured before startup")
        self._kernel.configure_initial_steering_curve(curve)

    def configure_initial_button_profile(
        self,
        profile: ActiveButtonProfile,
        saved_profile_revision: int | None = None,
    ) -> None:
        if self._started:
            raise RuntimeError("initial button profile must be configured before startup")
        self._kernel.configure_initial_button_profile(profile, saved_profile_revision)

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

        execution = self._dispatch(KernelStarted(self._clock()))
        if execution is None:
            raise RuntimeError("live controller kernel did not start")

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

    def shutdown(self, now: float) -> RuntimeExecution | None:
        self._reader_stop.set()
        execution = self._dispatch(ShutdownRequested(now)) if self._started else None
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
        return application, diagnostics, ControllerAdapterSnapshot(simulation_session_id=None)

    @property
    def terminal(self) -> bool:
        return self._kernel.health.fatal

    def _dispatch(self, work: ControllerInput) -> RuntimeExecution | None:
        commit = self._kernel.dispatch(work)
        return (
            None
            if commit is None
            else RuntimeExecution(changed_topics=commit.changed_topics, commit_count=1)
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
