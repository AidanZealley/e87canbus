"""Small ISO-TP adapter between project CAN frames and ``can-isotp``."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable

import isotp

from e87canbus.protocol.can import CanFrame

MAXIMUM_PAYLOAD_LENGTH = 256


class IsoTpEndpoint:
    """One bounded, point-to-point ISO-TP link with private RX/TX state."""

    def __init__(
        self,
        *,
        tx_id: int,
        rx_id: int,
        send_frame: Callable[[CanFrame], None],
        maximum_payload_length: int = MAXIMUM_PAYLOAD_LENGTH,
    ) -> None:
        if maximum_payload_length != MAXIMUM_PAYLOAD_LENGTH:
            raise ValueError("ISO-TP maximum payload length must be 256")
        self._rx_frames: deque[isotp.CanMessage] = deque()
        self._completed: deque[bytes] = deque()
        self._errors: deque[Exception] = deque()
        self._maximum_payload_length = maximum_payload_length
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

        if frame.is_extended_id or len(frame.data) > 8 or not self._layer.address.is_for_me(
            isotp.CanMessage(frame.arbitration_id, len(frame.data), frame.data, False)
        ):
            return False
        self._rx_frames.append(
            isotp.CanMessage(frame.arbitration_id, len(frame.data), frame.data, False)
        )
        return True

    def send(self, payload: bytes) -> bool:
        """Start a transfer, returning false instead of interleaving when busy."""

        if len(payload) > self._maximum_payload_length:
            raise ValueError("ISO-TP payload exceeds 256 bytes")
        if self._layer.transmitting():
            return False
        self._layer.send(payload)
        return True

    def poll(self) -> None:
        """Advance the package state machine and expose complete payloads only."""

        self._layer.process(rx_timeout=0)
        while self._layer.available():
            payload = self._layer.recv()
            if payload is not None and len(payload) <= self._maximum_payload_length:
                self._completed.append(bytes(payload))

    def receive_payload(self) -> bytes | None:
        return self._completed.popleft() if self._completed else None

    @property
    def transmitting(self) -> bool:
        return self._layer.transmitting()

    @property
    def errors(self) -> tuple[Exception, ...]:
        return tuple(self._errors)

    def _receive(self, timeout: float) -> isotp.CanMessage | None:
        del timeout
        return self._rx_frames.popleft() if self._rx_frames else None
