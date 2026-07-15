"""SocketCAN readers and the canonical live controller runtime adapter."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import Protocol, assert_never

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.application.controller import ApplicationSnapshot
from e87canbus.can_io import CanReceiver
from e87canbus.config import AppConfig, CanNetwork
from e87canbus.output import (
    CanEffectFailure,
    EffectExecutor,
    EffectFailure,
    SafeCanTransmitter,
    SteeringActuatorFailure,
)
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.runtime import (
    ActivateSteeringCurve,
    CanEffectExecutionFailed,
    CanReaderFailed,
    Commit,
    ControllerInput,
    CoordinatorKernel,
    DiagnosticSnapshot,
    InboxOverflowed,
    KernelStarted,
    ReceivedCanFrame,
    ShutdownRequested,
    SteeringActuatorFailed,
    TimerElapsed,
)
from e87canbus.service import RuntimeExecution, RuntimeInputSink

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
    CanReaderFailed,
    CanEffectExecutionFailed,
    SteeringActuatorFailed,
    InboxOverflowed,
    ShutdownRequested,
    ActivateSteeringCurve,
)


class ReaderInbox(Protocol):
    maxsize: int

    def put_nowait(self, item: ControllerInput) -> None: ...


class _ServiceReaderInbox:
    def __init__(self, sink: RuntimeInputSink, capacity: int) -> None:
        self._sink = sink
        self.maxsize = capacity

    def put_nowait(self, item: ControllerInput) -> None:
        if not self._sink(item):
            raise queue.Full


class InboxOverflow:
    """Atomically retain the fault that cannot fit in an already-full inbox."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._input: InboxOverflowed | None = None

    def latch(self, network: CanNetwork, failed_at: float, capacity: int) -> bool:
        with self._lock:
            if self._input is not None:
                return False
            self._input = InboxOverflowed(
                network,
                failed_at,
                f"live CAN inbox capacity {capacity} exceeded",
            )
            return True

    @property
    def kernel_input(self) -> InboxOverflowed | None:
        with self._lock:
            return self._input


def read_frames_into_queue(
    network: CanNetwork,
    bus: CanReceiver,
    inbox: ReaderInbox,
    stop: threading.Event,
    overflow: InboxOverflow,
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
                _enqueue_or_overflow(failed, inbox, stop, overflow, failed_at)
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
        _enqueue_or_overflow(
            ReceivedCanFrame(network=network, frame=frame, received_at=received_at),
            inbox,
            stop,
            overflow,
            received_at,
        )


def _enqueue_or_overflow(
    kernel_input: ReaderInput,
    inbox: ReaderInbox,
    stop: threading.Event,
    overflow: InboxOverflow,
    failed_at: float,
) -> None:
    try:
        inbox.put_nowait(kernel_input)
    except queue.Full:
        network = kernel_input.network
        if overflow.latch(network, failed_at, inbox.maxsize):
            LOGGER.error(
                "live CAN inbox overflow; stopping: network=%s capacity=%d",
                network.value,
                inbox.maxsize,
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
        _effect_failure_input(failure, clock())
        for failure in executor.execute(commit.effects)
    )


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


class LiveControllerRuntime:
    """SocketCAN reader/effect adapter selected behind ``ControllerService``."""

    def __init__(
        self,
        config: AppConfig,
        *,
        tx_grants: frozenset[CanNetwork] = frozenset(),
        bus_factory: Callable[[str], SocketCanBus] = SocketCanBus,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        configured_tx = frozenset(
            item.network for item in config.can_networks if item.enabled and item.tx_enabled
        )
        if not configured_tx.issubset(tx_grants):
            missing = ", ".join(sorted(network.value for network in configured_tx - tx_grants))
            raise ValueError(f"live CAN TX requires an explicit network grant: {missing}")
        self.config = config
        self._tx_grants = tx_grants
        self._bus_factory = bus_factory
        self._clock = clock
        self._router = ProtocolRouter(config.custom_can_ids)
        self._kernel = CoordinatorKernel(
            steering_config=config.steering,
            engine_telemetry_config=config.engine_telemetry,
            router=self._router,
        )
        self._executor = EffectExecutor(router=self._router)
        self._raw_buses: dict[CanNetwork, SocketCanBus] = {}
        self._readers: list[threading.Thread] = []
        self._reader_stop = threading.Event()
        self._overflow = InboxOverflow()
        self._started = False

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
            if item.tx_enabled and item.network in self._tx_grants
        }
        self._executor = EffectExecutor(transmitters, self._router)
        execution = self._dispatch(KernelStarted(self._clock()))
        if execution is None:
            raise RuntimeError("live controller kernel did not start")

        reader_inbox = _ServiceReaderInbox(submit_input, self.config.runtime_inbox_capacity)
        self._readers = [
            threading.Thread(
                target=read_frames_into_queue,
                args=(
                    item.network,
                    self._raw_buses[item.network],
                    reader_inbox,
                    self._reader_stop,
                    self._overflow,
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
        if not isinstance(work, CONTROLLER_INPUT_TYPES):
            raise TypeError(f"unsupported live controller work: {work!r}")
        if isinstance(work, ReceivedCanFrame):
            queue_latency_s = self._clock() - work.received_at
            if queue_latency_s > self.config.runtime_queue_latency_warning_s:
                LOGGER.warning(
                    "CAN frame waited in live inbox: network=%s latency_s=%.3f",
                    work.network.value,
                    queue_latency_s,
                )
        execution = self._dispatch(work)
        return execution or self._current_execution(None)

    def timer(self, now: float) -> RuntimeExecution | None:
        overflow = self._overflow.kernel_input
        if overflow is not None:
            return self._dispatch(overflow)
        return self._dispatch(TimerElapsed(now))

    def shutdown(self, now: float) -> RuntimeExecution | None:
        self._reader_stop.set()
        execution = self._dispatch(ShutdownRequested(now)) if self._started else None
        # Keep output capabilities available for the ordered safe-shutdown transition, then close
        # endpoints to unblock any receiver before requiring every reader to terminate.
        self._close_buses()
        for reader in self._readers:
            reader.join(timeout=READER_JOIN_TIMEOUT_S)
        alive = tuple(reader.name for reader in self._readers if reader.is_alive())
        if alive:
            names = ", ".join(alive)
            raise RuntimeError(f"live CAN readers did not stop after adapter close: {names}")
        return execution

    def projection(self) -> tuple[int, ApplicationSnapshot, DiagnosticSnapshot]:
        diagnostics = self._kernel.diagnostics()
        return diagnostics.revision, self._kernel.snapshot(), diagnostics

    @property
    def terminal(self) -> bool:
        return self._kernel.health.fatal

    def _dispatch(self, work: ControllerInput) -> RuntimeExecution | None:
        commit = self._kernel.dispatch(work)
        failures = _execute(commit, self._executor, self._clock)
        for failure in failures:
            self._kernel.dispatch(failure)
        return None if commit is None else self._current_execution(commit)

    def _current_execution(self, result: object) -> RuntimeExecution:
        return RuntimeExecution(result, self._kernel.snapshot())

    def _close_buses(self) -> None:
        for network, bus in tuple(self._raw_buses.items()):
            try:
                bus.shutdown()
            except OSError as exc:
                LOGGER.error("failed to close SocketCAN network %s: %s", network.value, exc)
        self._raw_buses.clear()
