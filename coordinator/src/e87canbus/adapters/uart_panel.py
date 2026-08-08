"""Nonblocking Raspberry Pi UART adapter for the coordinator panel."""

from __future__ import annotations

import os
import termios
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Protocol, TypeAlias

from e87canbus.local_controls.model import (
    LocalControlsEvent,
    PanelAdapterFailed,
    PanelButtonPressed,
    PanelDisplayState,
    PanelLink,
    PanelLinkChanged,
)
from e87canbus.local_controls.ports import LocalControlsInputSink

PANEL_UART_DEVICE = "/dev/serial0"
_PROTOCOL_PREFIX = ("PANEL", "1")
_MAX_SEQUENCE = 0xFFFF_FFFF
_DEFAULT_MAX_LINE_BYTES = 64
_DEFAULT_READ_BUDGET_BYTES = 512
_DEFAULT_RECONNECT_INTERVAL_S = 1.0
_MAX_WRITE_CALLS_PER_POLL = 2
_MAX_WRITE_CALLS_ON_CLOSE = 64
_MAX_DIAGNOSTIC_BYTES = 160


class _SerialConnection(Protocol):
    def read(self, size: int) -> bytes: ...
    def write(self, data: bytes) -> int: ...
    def close(self) -> None: ...


_SerialOpener: TypeAlias = Callable[[str], _SerialConnection]


@dataclass(frozen=True)
class UartPanelDiagnostics:
    """Small bounded snapshot suitable for local troubleshooting."""

    link: PanelLink
    successful_connections: int
    invalid_lines: int
    oversized_lines: int
    last_error: str | None


class UartPanel:
    """Translate the version 1 panel protocol without owning product policy."""

    def __init__(
        self,
        *,
        device: str = PANEL_UART_DEVICE,
        reconnect_interval_s: float = _DEFAULT_RECONNECT_INTERVAL_S,
        max_line_bytes: int = _DEFAULT_MAX_LINE_BYTES,
        read_budget_bytes: int = _DEFAULT_READ_BUDGET_BYTES,
        opener: _SerialOpener | None = None,
    ) -> None:
        if reconnect_interval_s <= 0:
            raise ValueError("reconnect_interval_s must be positive")
        if max_line_bytes < 1 or read_budget_bytes < 1:
            raise ValueError("UART input bounds must be positive")

        self._device = device
        self._reconnect_interval_s = reconnect_interval_s
        self._max_line_bytes = max_line_bytes
        self._read_budget_bytes = read_budget_bytes
        self._opener = opener or _open_serial

        self._submit: LocalControlsInputSink | None = None
        self._connection: _SerialConnection | None = None
        self._next_connect_at = 0.0
        self._last_poll_at = 0.0
        self._latest_display = PanelDisplayState.STARTING
        self._receive_buffer = bytearray()
        self._discarding_oversized_line = False
        self._transmit = b""
        self._transmit_offset = 0
        self._next_transmit: bytes | None = None
        self._last_wire_sequence: int | None = None
        self._delivered_sequence = 0
        self._pending_button: PanelButtonPressed | None = None
        self._pending_link_event: LocalControlsEvent | None = None

        self._successful_connections = 0
        self._invalid_lines = 0
        self._oversized_lines = 0
        self._last_error: str | None = None

    @property
    def diagnostics(self) -> UartPanelDiagnostics:
        return UartPanelDiagnostics(
            link=(
                PanelLink.CONNECTED
                if self._connection is not None
                else PanelLink.DISCONNECTED
            ),
            successful_connections=self._successful_connections,
            invalid_lines=self._invalid_lines,
            oversized_lines=self._oversized_lines,
            last_error=self._last_error,
        )

    def start(self, submit: LocalControlsInputSink) -> None:
        if self._submit is not None:
            raise RuntimeError("UART panel adapter is already started")
        self._submit = submit

    def set_display(self, display: PanelDisplayState) -> None:
        self._latest_display = display
        if self._connection is not None:
            self._queue_latest_state()
            self._flush_output()

    def poll(self, now: float) -> None:
        self._last_poll_at = now
        if self._submit is None:
            return
        # Report the previous I/O failure before a due reconnect can replace it
        # with the newer connected observation.
        self._submit_pending_link_event()
        if self._connection is None and now >= self._next_connect_at:
            self._connect(now)
        if self._connection is None:
            self._submit_pending_link_event()
            return

        self._submit_pending_link_event()
        self._submit_pending_button()
        self._read_input(now)
        if self._connection is not None:
            self._flush_output(now)

    def close(self) -> None:
        if self._connection is not None:
            self._flush_output(
                max_calls=_MAX_WRITE_CALLS_ON_CLOSE,
                retry_would_block=True,
            )
        self._close_connection()
        self._submit = None
        self._pending_link_event = None

    def _connect(self, now: float) -> None:
        try:
            connection = self._opener(self._device)
        except OSError as exc:
            self._record_failure("open", exc, now)
            return

        self._connection = connection
        self._successful_connections += 1
        self._last_error = None
        self._receive_buffer.clear()
        self._discarding_oversized_line = False
        self._last_wire_sequence = None
        self._transmit = b""
        self._transmit_offset = 0
        self._next_transmit = None
        self._pending_link_event = PanelLinkChanged(PanelLink.CONNECTED)
        self._queue_latest_state()

    def _read_input(self, now: float) -> None:
        connection = self._connection
        assert connection is not None
        remaining = self._read_budget_bytes
        while remaining > 0:
            try:
                chunk = connection.read(remaining)
            except BlockingIOError:
                return
            except OSError as exc:
                self._record_failure("read", exc, now)
                return
            if not chunk:
                return
            remaining -= len(chunk)
            self._consume_input(chunk)

    def _consume_input(self, chunk: bytes) -> None:
        for byte in chunk:
            if byte == ord("\n"):
                self._finish_line()
            elif self._discarding_oversized_line:
                continue
            elif len(self._receive_buffer) >= self._max_line_bytes:
                self._receive_buffer.clear()
                self._discarding_oversized_line = True
                self._oversized_lines += 1
            else:
                self._receive_buffer.append(byte)

    def _finish_line(self) -> None:
        if self._discarding_oversized_line:
            self._discarding_oversized_line = False
            return
        line = bytes(self._receive_buffer).removesuffix(b"\r")
        self._receive_buffer.clear()
        if not line:
            return
        try:
            fields = line.decode("ascii").split()
        except UnicodeDecodeError:
            self._invalid_lines += 1
            return
        self._handle_fields(fields)

    def _handle_fields(self, fields: list[str]) -> None:
        if fields == [*_PROTOCOL_PREFIX, "HELLO"]:
            # HELLO starts a new wire sequence session. A press awaiting delivery belongs
            # to the previous connection and must not be replayed into the new session.
            self._last_wire_sequence = None
            self._pending_button = None
            self._queue_latest_state()
            return
        if len(fields) != 4 or tuple(fields[:2]) != _PROTOCOL_PREFIX:
            self._invalid_lines += 1
            return
        if fields[2] != "BUTTON" or not fields[3].isascii() or not fields[3].isdigit():
            self._invalid_lines += 1
            return
        sequence = int(fields[3])
        if sequence > _MAX_SEQUENCE:
            self._invalid_lines += 1
            return
        if sequence == self._last_wire_sequence:
            return
        self._last_wire_sequence = sequence
        if self._pending_button is not None:
            # The protocol does not replay or queue missed physical presses. Preserve the
            # older press already waiting for the service and discard this later one.
            return
        self._delivered_sequence = (self._delivered_sequence + 1) & _MAX_SEQUENCE
        self._pending_button = PanelButtonPressed(self._delivered_sequence)
        self._submit_pending_button()

    def _queue_latest_state(self) -> None:
        line = f"PANEL 1 STATE {self._latest_display.value}\n".encode("ascii")
        if not self._transmit:
            self._transmit = line
            self._transmit_offset = 0
        elif self._transmit_offset == 0:
            self._transmit = line
        else:
            # Complete the partially written line, then send only the newest state.
            self._next_transmit = line

    def _flush_output(
        self,
        now: float | None = None,
        *,
        max_calls: int = _MAX_WRITE_CALLS_PER_POLL,
        retry_would_block: bool = False,
    ) -> None:
        now = self._last_poll_at if now is None else now
        connection = self._connection
        assert connection is not None
        calls = 0
        while self._transmit and calls < max_calls:
            calls += 1
            try:
                written = connection.write(self._transmit[self._transmit_offset :])
            except BlockingIOError:
                if retry_would_block:
                    continue
                return
            except OSError as exc:
                self._record_failure("write", exc, now)
                return
            if written <= 0:
                return
            self._transmit_offset += written
            if self._transmit_offset < len(self._transmit):
                continue
            if self._next_transmit is None:
                self._transmit = b""
                self._transmit_offset = 0
            else:
                self._transmit = self._next_transmit
                self._transmit_offset = 0
                self._next_transmit = None

    def _record_failure(self, action: str, exc: OSError, now: float) -> None:
        message = f"panel UART {action} failed: {exc}"[:_MAX_DIAGNOSTIC_BYTES]
        self._last_error = message
        self._pending_link_event = PanelAdapterFailed(message)
        self._next_connect_at = now + self._reconnect_interval_s
        self._close_connection()

    def _submit_pending_link_event(self) -> None:
        event = self._pending_link_event
        submit = self._submit
        if event is not None and submit is not None and submit(event):
            self._pending_link_event = None

    def _submit_pending_button(self) -> None:
        event = self._pending_button
        submit = self._submit
        if event is not None and submit is not None and submit(event):
            self._pending_button = None

    def _close_connection(self) -> None:
        connection, self._connection = self._connection, None
        self._transmit = b""
        self._transmit_offset = 0
        self._next_transmit = None
        self._pending_button = None
        self._last_wire_sequence = None
        if connection is not None:
            with suppress(OSError):
                connection.close()


class _PosixSerialConnection:
    def __init__(self, file_descriptor: int) -> None:
        self._file_descriptor = file_descriptor

    def read(self, size: int) -> bytes:
        return os.read(self._file_descriptor, size)

    def write(self, data: bytes) -> int:
        return os.write(self._file_descriptor, data)

    def close(self) -> None:
        os.close(self._file_descriptor)


def _open_serial(device: str) -> _SerialConnection:
    file_descriptor = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        attributes = termios.tcgetattr(file_descriptor)
        attributes[0] = 0
        attributes[1] = 0
        attributes[2] = termios.CS8 | termios.CLOCAL | termios.CREAD
        attributes[3] = 0
        attributes[4] = termios.B115200
        attributes[5] = termios.B115200
        attributes[6][termios.VMIN] = 0
        attributes[6][termios.VTIME] = 0
        termios.tcsetattr(file_descriptor, termios.TCSANOW, attributes)
        termios.tcflush(file_descriptor, termios.TCIOFLUSH)
    except Exception:
        os.close(file_descriptor)
        raise
    return _PosixSerialConnection(file_descriptor)
