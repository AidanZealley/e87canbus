"""Live SocketCAN composition and coordinator loop."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.can_io import CanReceiver
from e87canbus.config import AppConfig, CanNetwork
from e87canbus.output import EffectExecutor, SafeCanTransmitter
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.runtime import CoordinatorRuntime, ReceivedCanFrame

LOGGER = logging.getLogger(__name__)

MIN_QUEUE_TIMEOUT_S = 0.001
MAX_MISSED_TICKS = 3
READER_JOIN_TIMEOUT_S = 1.0
INITIAL_READER_ERROR_BACKOFF_S = 0.05
MAX_READER_ERROR_BACKOFF_S = 1.0


class InboxOverflow:
    """Atomically record the first network that overflows the live inbox."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._network: CanNetwork | None = None

    def latch(self, network: CanNetwork) -> bool:
        with self._lock:
            if self._network is not None:
                return False
            self._network = network
            return True

    @property
    def occurred(self) -> bool:
        with self._lock:
            return self._network is not None


def read_frames_into_queue(
    network: CanNetwork,
    bus: CanReceiver,
    frames: queue.Queue[ReceivedCanFrame],
    stop: threading.Event,
    overflow: InboxOverflow,
    clock: Callable[[], float] = time.monotonic,
    receive_timeout_s: float = 0.2,
) -> None:
    """Read and timestamp one CAN interface until shutdown."""

    error_backoff_s = INITIAL_READER_ERROR_BACKOFF_S
    while not stop.is_set():
        try:
            frame = bus.receive(timeout_s=receive_timeout_s)
        except OSError as exc:
            LOGGER.warning(
                "failed to receive CAN frame and continued: network=%s error=%s",
                network,
                exc,
            )
            stop.wait(error_backoff_s)
            error_backoff_s = min(error_backoff_s * 2, MAX_READER_ERROR_BACKOFF_S)
            continue
        error_backoff_s = INITIAL_READER_ERROR_BACKOFF_S
        if frame is None:
            continue

        received = ReceivedCanFrame(network=network, frame=frame, received_at=clock())
        try:
            frames.put_nowait(received)
        except queue.Full:
            if overflow.latch(network):
                LOGGER.error(
                    "live CAN inbox overflow; stopping: network=%s capacity=%d",
                    network.value,
                    frames.maxsize,
                )
            stop.set()
            return


def run_coordinator_loop(
    runtime: CoordinatorRuntime,
    frames: queue.Queue[ReceivedCanFrame],
    stop: threading.Event,
    tick_interval_s: float,
    queue_latency_warning_s: float,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Process live frames and periodic ticks on the calling thread."""

    runtime.start()
    next_tick = clock() + tick_interval_s
    while not stop.is_set():
        timeout_s = max(next_tick - clock(), MIN_QUEUE_TIMEOUT_S)
        try:
            received = frames.get(timeout=timeout_s)
        except queue.Empty:
            pass
        else:
            if stop.is_set():
                break
            processing_started_at = clock()
            queue_latency_s = processing_started_at - received.received_at
            if queue_latency_s > queue_latency_warning_s:
                LOGGER.warning(
                    "CAN frame waited in live inbox: network=%s latency_s=%.3f",
                    received.network.value,
                    queue_latency_s,
                )
            runtime.process_frame(received)

        now = clock()
        if now < next_tick:
            continue

        runtime.tick()
        next_tick += tick_interval_s
        if now - next_tick > MAX_MISSED_TICKS * tick_interval_s:
            # Catch-up tick bursts delay useful frame processing after a long stall.
            next_tick = now + tick_interval_s


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
    runtime = CoordinatorRuntime(
        receivers=raw_buses,
        steering_config=config.steering,
        router=router,
        executor=EffectExecutor(transmitters, router),
    )
    frames: queue.Queue[ReceivedCanFrame] = queue.Queue(
        maxsize=config.runtime_inbox_capacity
    )
    stop = threading.Event()
    overflow = InboxOverflow()
    readers = [
        threading.Thread(
            target=read_frames_into_queue,
            args=(item.network, raw_buses[item.network], frames, stop, overflow),
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

    try:
        run_coordinator_loop(
            runtime,
            frames,
            stop,
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
    return 1 if overflow.occurred else 0
