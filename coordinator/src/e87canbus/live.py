"""Live SocketCAN composition and coordinator loop."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from contextlib import suppress

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.config import AppConfig, CanNetwork
from e87canbus.protocol.can import CanBus, RateLimitedCanBus, RoutedCanFrame
from e87canbus.runtime import CoordinatorRuntime

LOGGER = logging.getLogger(__name__)

MIN_QUEUE_TIMEOUT_S = 0.001
MAX_MISSED_TICKS = 3
READER_JOIN_TIMEOUT_S = 1.0
INITIAL_READER_ERROR_BACKOFF_S = 0.05
MAX_READER_ERROR_BACKOFF_S = 1.0


def read_frames_into_queue(
    network: CanNetwork,
    bus: CanBus,
    frames: queue.Queue[RoutedCanFrame],
    stop: threading.Event,
    receive_timeout_s: float = 0.2,
) -> None:
    """Read one CAN interface until shutdown and tag frames with its network."""

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
        if frame is not None:
            frames.put(RoutedCanFrame(network=network, frame=frame))


def run_coordinator_loop(
    runtime: CoordinatorRuntime,
    frames: queue.Queue[RoutedCanFrame],
    stop: threading.Event,
    tick_interval_s: float,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Process live frames and periodic ticks on the calling thread."""

    runtime.start()
    next_tick = clock() + tick_interval_s
    while not stop.is_set():
        timeout_s = max(next_tick - clock(), MIN_QUEUE_TIMEOUT_S)
        with suppress(queue.Empty):
            runtime.process_frame(frames.get(timeout=timeout_s))

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
    buses: dict[CanNetwork, CanBus] = {}
    try:
        for item in enabled:
            raw_bus = SocketCanBus(item.interface)
            raw_buses[item.network] = raw_bus
            buses[item.network] = (
                RateLimitedCanBus(raw_bus, config.tx_policy) if item.tx_enabled else raw_bus
            )
    except OSError as exc:
        LOGGER.error("failed to open SocketCAN interface %s: %s", item.interface, exc)
        for raw_bus in raw_buses.values():
            raw_bus.shutdown()
        return 1

    tx_networks = frozenset(item.network for item in enabled if item.tx_enabled)
    runtime = CoordinatorRuntime(buses=buses, tx_networks=tx_networks)
    frames: queue.Queue[RoutedCanFrame] = queue.Queue()
    stop = threading.Event()
    readers = [
        threading.Thread(
            target=read_frames_into_queue,
            args=(item.network, buses[item.network], frames, stop),
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
        run_coordinator_loop(runtime, frames, stop, config.tick_interval_s)
    except KeyboardInterrupt:
        LOGGER.info("stopping live coordinator")
    finally:
        stop.set()
        for reader in readers:
            reader.join(timeout=READER_JOIN_TIMEOUT_S)
        for raw_bus in raw_buses.values():
            raw_bus.shutdown()
    return 0
