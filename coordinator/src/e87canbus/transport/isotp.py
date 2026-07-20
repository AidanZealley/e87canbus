"""Small ISO-TP adapter between project CAN frames and ``can-isotp``."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

import isotp

from e87canbus.protocol.can import CanFrame

MAXIMUM_PAYLOAD_LENGTH = 64


class IsoTpEndpoint:
    """One bounded, point-to-point ISO-TP link with private RX/TX state.

    TX follows latest-value semantics: send() always accepts the new payload,
    overwriting any not-yet-dispatched pending payload. poll() dispatches the
    pending payload as soon as the layer becomes idle. This decouples callers
    from transport timing — there is no "busy" condition to handle.
    """

    def __init__(
        self,
        *,
        tx_id: int,
        rx_id: int,
        send_frame: Callable[[CanFrame], None],
        maximum_payload_length: int = MAXIMUM_PAYLOAD_LENGTH,
        minimum_payload_interval_s: float = 0.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if maximum_payload_length != MAXIMUM_PAYLOAD_LENGTH:
            raise ValueError("ISO-TP maximum payload length must be 64")
        self._rx_frames: deque[isotp.CanMessage] = deque()
        self._completed: deque[bytes] = deque()
        self._errors: deque[Exception] = deque()
        self._maximum_payload_length = maximum_payload_length
        if minimum_payload_interval_s < 0:
            raise ValueError("ISO-TP minimum payload interval cannot be negative")
        self._minimum_payload_interval_s = minimum_payload_interval_s
        self._clock = clock
        self._next_payload_at = 0.0
        self._pending: deque[bytes] = deque()
        self._layer = isotp.TransportLayer(
            rxfn=self._receive,
            txfn=lambda message: send_frame(
                CanFrame(message.arbitration_id, bytes(message.data), message.is_extended_id)
            ),
            address=isotp.Address(isotp.AddressingMode.Normal_11bits, txid=tx_id, rxid=rx_id),
            error_handler=self._errors.append,
            params={"max_frame_size": maximum_payload_length, "blocking_send": False},
        )

    def on_frame(self, frame: CanFrame) -> bool:
        """Accept a matching standard frame for later non-blocking processing."""

        if (
            frame.is_extended_id
            or len(frame.data) > 8
            or not self._layer.address.is_for_me(
                isotp.CanMessage(frame.arbitration_id, len(frame.data), frame.data, False)
            )
        ):
            return False
        self._rx_frames.append(
            isotp.CanMessage(frame.arbitration_id, len(frame.data), frame.data, False)
        )
        return True

    def send(self, payload: bytes) -> None:
        """Buffer the latest payload for transmission; poll() dispatches when idle."""

        if len(payload) > self._maximum_payload_length:
            raise ValueError("ISO-TP payload exceeds 64 bytes")
        self._pending.clear()
        self._pending.append(payload)

    def send_many(self, payloads: tuple[bytes, ...]) -> None:
        """Replace pending work with one ordered latest-value program."""
        if not payloads or any(len(payload) > self._maximum_payload_length for payload in payloads):
            raise ValueError("ISO-TP program must contain bounded payloads")
        self._pending.clear()
        self._pending.extend(payloads)

    def poll(self) -> None:
        """Advance the ISO-TP state machine; dispatch pending payload when idle."""

        self._layer.process(rx_timeout=0)
        now = self._clock()
        if self._pending and not self._layer.transmitting() and now >= self._next_payload_at:
            self._layer.send(self._pending.popleft())
            self._next_payload_at = now + self._minimum_payload_interval_s
            self._layer.process(rx_timeout=0)
        while self._layer.available():
            payload = self._layer.recv()
            if payload is not None and len(payload) <= self._maximum_payload_length:
                self._completed.append(bytes(payload))

    def receive_payload(self) -> bytes | None:
        return self._completed.popleft() if self._completed else None

    @property
    def transmitting(self) -> bool:
        return self._layer.transmitting() or bool(self._pending)

    @property
    def errors(self) -> tuple[Exception, ...]:
        return tuple(self._errors)

    def _receive(self, timeout: float) -> isotp.CanMessage | None:
        del timeout
        return self._rx_frames.popleft() if self._rx_frames else None
