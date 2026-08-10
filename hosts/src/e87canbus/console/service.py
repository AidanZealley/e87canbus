"""Small receive-only K-CAN owner for the console host."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from e87canbus.adapters.can_io import CanReceiver

LOGGER = logging.getLogger(__name__)


class ManagedCanReceiver(CanReceiver, Protocol):
    """The receive capability plus the lifecycle operation owned by composition."""

    def shutdown(self) -> None:
        """Close the receiver and release its operating-system resources."""


@dataclass(frozen=True)
class ConsoleServiceSnapshot:
    boot_id: str
    revision: int
    connected: bool
    frames_received: int
    fault: str | None


class ConsoleCanService:
    """Open, monitor, and close exactly one receive-only K-CAN endpoint."""

    def __init__(
        self,
        receiver_factory: Callable[[], ManagedCanReceiver],
        *,
        receive_timeout_s: float = 0.1,
        shutdown_timeout_s: float = 1.0,
    ) -> None:
        self._receiver_factory = receiver_factory
        self._receive_timeout_s = receive_timeout_s
        self._shutdown_timeout_s = shutdown_timeout_s
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._receiver: ManagedCanReceiver | None = None
        self._receiver_closed = True
        self._reader: threading.Thread | None = None
        self._listener: Callable[[ConsoleServiceSnapshot], None] | None = None
        self._started = False
        self._snapshot = ConsoleServiceSnapshot(
            boot_id=uuid4().hex,
            revision=0,
            connected=False,
            frames_received=0,
            fault=None,
        )

    @property
    def ready(self) -> bool:
        snapshot = self.snapshot()
        reader = self._reader
        return (
            snapshot.connected
            and snapshot.fault is None
            and reader is not None
            and reader.is_alive()
        )

    def snapshot(self) -> ConsoleServiceSnapshot:
        with self._lock:
            return self._snapshot

    def start(self, listener: Callable[[ConsoleServiceSnapshot], None]) -> None:
        if self._started:
            raise RuntimeError("console CAN service may be started exactly once")
        self._started = True
        self._listener = listener
        try:
            receiver = self._receiver_factory()
        except Exception as exc:
            self._replace(connected=False, fault=f"failed to open kcan: {exc}")
            return

        self._receiver = receiver
        self._receiver_closed = False
        self._replace(connected=True, fault=None)
        self._reader = threading.Thread(
            target=self._run,
            name="console-kcan-reader",
        )
        self._reader.start()

    def stop(self) -> None:
        self._stop.set()
        reader = self._reader
        if reader is not None:
            reader.join(timeout=self._shutdown_timeout_s)
        self._close_receiver()
        if reader is not None and reader.is_alive():
            reader.join(timeout=self._shutdown_timeout_s)
        if reader is not None and reader.is_alive():
            raise RuntimeError("console K-CAN reader did not stop within its deadline")
        with self._lock:
            current = self._snapshot
            if current.connected:
                self._snapshot = ConsoleServiceSnapshot(
                    boot_id=current.boot_id,
                    revision=current.revision + 1,
                    connected=False,
                    frames_received=current.frames_received,
                    fault=current.fault,
                )
        self._receiver = None
        self._reader = None

    def _run(self) -> None:
        receiver = self._receiver
        assert receiver is not None
        while not self._stop.is_set():
            try:
                frame = receiver.receive(timeout_s=self._receive_timeout_s)
            except Exception as exc:
                if not self._stop.is_set():
                    self._replace(connected=False, fault=f"kcan receive failed: {exc}")
                    self._close_receiver()
                return
            if frame is not None:
                self._increment_frames()

    def _increment_frames(self) -> None:
        with self._lock:
            current = self._snapshot
            snapshot = ConsoleServiceSnapshot(
                boot_id=current.boot_id,
                revision=current.revision + 1,
                connected=current.connected,
                frames_received=current.frames_received + 1,
                fault=current.fault,
            )
            self._snapshot = snapshot
        self._notify(snapshot)

    def _replace(self, *, connected: bool, fault: str | None) -> None:
        with self._lock:
            current = self._snapshot
            snapshot = ConsoleServiceSnapshot(
                boot_id=current.boot_id,
                revision=current.revision + 1,
                connected=connected,
                frames_received=current.frames_received,
                fault=fault,
            )
            self._snapshot = snapshot
        self._notify(snapshot)

    def _notify(self, snapshot: ConsoleServiceSnapshot) -> None:
        listener = self._listener
        if listener is None:
            return
        try:
            listener(snapshot)
        except Exception:
            # Browser publication is diagnostic and must never become CAN reader failure.
            LOGGER.warning("Console live-state listener failed", exc_info=True)

    def _close_receiver(self) -> None:
        with self._lock:
            if self._receiver is None or self._receiver_closed:
                return
            receiver = self._receiver
            self._receiver_closed = True
        try:
            receiver.shutdown()
        except Exception:
            LOGGER.warning("Failed to close console K-CAN receiver", exc_info=True)
