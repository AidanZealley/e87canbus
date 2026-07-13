"""Live SocketCAN composition and single-consumer kernel loop."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.application.events import ControlTimerElapsed
from e87canbus.can_io import CanReceiver
from e87canbus.config import AppConfig, CanNetwork
from e87canbus.output import EffectExecutor, SafeCanTransmitter
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.runtime import (
    CanReaderFailed,
    Commit,
    CoordinatorKernel,
    EffectExecutionFailed,
    InboxOverflowed,
    KernelInput,
    KernelStarted,
    ReceivedCanFrame,
    ShutdownRequested,
)

LOGGER = logging.getLogger(__name__)

MIN_QUEUE_TIMEOUT_S = 0.001
MAX_MISSED_TICKS = 3
READER_JOIN_TIMEOUT_S = 1.0
MAX_CONSECUTIVE_READER_ERRORS = 3
INITIAL_READER_ERROR_BACKOFF_S = 0.05

ReaderInput = ReceivedCanFrame | CanReaderFailed


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
    inbox: queue.Queue[KernelInput],
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
    inbox: queue.Queue[KernelInput],
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


def run_coordinator_loop(
    kernel: CoordinatorKernel,
    executor: EffectExecutor,
    inbox: queue.Queue[KernelInput],
    stop: threading.Event,
    overflow: InboxOverflow,
    tick_interval_s: float,
    queue_latency_warning_s: float,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """Dispatch ordered live inputs and execute committed effects on this thread."""

    pending_failures = _execute(kernel.dispatch(KernelStarted(clock())), executor, clock)
    next_tick = clock() + tick_interval_s
    try:
        while True:
            overflow_input = overflow.kernel_input
            if overflow_input is not None:
                kernel.dispatch(overflow_input)
                return True

            if pending_failures:
                for failure in pending_failures:
                    kernel.dispatch(failure)
                return True

            if stop.is_set():
                return kernel.health.fatal

            timeout_s = max(next_tick - clock(), MIN_QUEUE_TIMEOUT_S)
            try:
                kernel_input = inbox.get(timeout=timeout_s)
            except queue.Empty:
                kernel_input = None

            if isinstance(kernel_input, ReceivedCanFrame):
                queue_latency_s = clock() - kernel_input.received_at
                if queue_latency_s > queue_latency_warning_s:
                    LOGGER.warning(
                        "CAN frame waited in live inbox: network=%s latency_s=%.3f",
                        kernel_input.network.value,
                        queue_latency_s,
                    )

            if kernel_input is not None:
                pending_failures = _execute(
                    kernel.dispatch(kernel_input),
                    executor,
                    clock,
                )
                if kernel.health.fatal:
                    return True

            now = clock()
            if now < next_tick:
                continue

            pending_failures = _execute(
                kernel.dispatch(ControlTimerElapsed(now)),
                executor,
                clock,
            )
            next_tick += tick_interval_s
            if now - next_tick > MAX_MISSED_TICKS * tick_interval_s:
                # Catch-up tick bursts delay useful frame processing after a long stall.
                next_tick = now + tick_interval_s
    finally:
        kernel.dispatch(ShutdownRequested(clock()))


def _execute(
    commit: Commit | None,
    executor: EffectExecutor,
    clock: Callable[[], float],
) -> tuple[EffectExecutionFailed, ...]:
    if commit is None:
        return ()
    return tuple(
        EffectExecutionFailed(failure.network, clock(), failure.message)
        for failure in executor.execute(commit.effects)
    )


def run_live(config: AppConfig) -> int:
    """Open configured SocketCAN interfaces and run until interrupted."""

    enabled = tuple(item for item in config.can_networks if item.enabled)
    raw_buses: dict[CanNetwork, SocketCanBus] = {}
    try:
        for item in enabled:
            raw_buses[item.network] = SocketCanBus(item.interface)
    except OSError as exc:
        LOGGER.error("failed to open SocketCAN interface %s: %s", item.interface, exc)
        for raw_bus in raw_buses.values():
            raw_bus.shutdown()
        return 1

    router = ProtocolRouter(config.custom_can_ids)
    transmitters = {
        item.network: SafeCanTransmitter(raw_buses[item.network], config.tx_policy)
        for item in enabled
        if item.tx_enabled
    }
    kernel = CoordinatorKernel(
        steering_config=config.steering,
        router=router,
    )
    executor = EffectExecutor(transmitters, router)
    inbox: queue.Queue[KernelInput] = queue.Queue(maxsize=config.runtime_inbox_capacity)
    stop = threading.Event()
    overflow = InboxOverflow()
    readers = [
        threading.Thread(
            target=read_frames_into_queue,
            args=(item.network, raw_buses[item.network], inbox, stop, overflow),
            daemon=True,
            name=f"{item.network.value}-reader",
        )
        for item in enabled
    ]

    tx_names = ", ".join(item.network.value for item in enabled if item.tx_enabled) or "none"
    rx_only_names = (
        ", ".join(item.network.value for item in enabled if not item.tx_enabled) or "none"
    )
    LOGGER.info("application TX enabled: %s | application TX disabled: %s", tx_names, rx_only_names)

    for reader in readers:
        reader.start()

    failed = False
    try:
        failed = run_coordinator_loop(
            kernel,
            executor,
            inbox,
            stop,
            overflow,
            config.tick_interval_s,
            config.runtime_queue_latency_warning_s,
        )
    except KeyboardInterrupt:
        LOGGER.info("stopping live coordinator")
    finally:
        stop.set()
        for reader in readers:
            reader.join(timeout=READER_JOIN_TIMEOUT_S)
        for raw_bus in raw_buses.values():
            raw_bus.shutdown()
    return 1 if failed else 0
