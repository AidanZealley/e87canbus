from __future__ import annotations

import isotp.protocol
import pytest
from e87canbus.config import CanNetwork
from e87canbus.protocol.can import CanFrame
from e87canbus.protocol.generated import (
    BUTTON_PAD_TRANSPORT_MAXIMUM_PAYLOAD_LENGTH,
    CAN_ID_BUTTON_PAD_TRANSPORT_COORDINATOR_TO_DEVICE,
    CAN_ID_BUTTON_PAD_TRANSPORT_DEVICE_TO_COORDINATOR,
)
from e87canbus.simulation.bus import InMemoryCanTopology
from e87canbus.transport.isotp import IsoTpEndpoint


def _endpoints() -> tuple[IsoTpEndpoint, IsoTpEndpoint]:
    topology = InMemoryCanTopology(clock=lambda: 0.0)
    coordinator_bus = topology.create_bus(CanNetwork.KCAN, "coordinator")
    pad_bus = topology.create_bus(CanNetwork.KCAN, "button-pad")
    coordinator = IsoTpEndpoint(
        tx_id=CAN_ID_BUTTON_PAD_TRANSPORT_COORDINATOR_TO_DEVICE,
        rx_id=CAN_ID_BUTTON_PAD_TRANSPORT_DEVICE_TO_COORDINATOR,
        send_frame=coordinator_bus.send,
    )
    pad = IsoTpEndpoint(
        tx_id=CAN_ID_BUTTON_PAD_TRANSPORT_DEVICE_TO_COORDINATOR,
        rx_id=CAN_ID_BUTTON_PAD_TRANSPORT_COORDINATOR_TO_DEVICE,
        send_frame=pad_bus.send,
    )

    def pump() -> None:
        for _ in range(64):
            coordinator.poll()
            pad.poll()
            progressed = False
            for bus, endpoint in ((coordinator_bus, coordinator), (pad_bus, pad)):
                while (frame := bus.receive(0)) is not None:
                    endpoint.on_frame(frame)
                    progressed = True
            if not progressed and not coordinator.transmitting and not pad.transmitting:
                return
        raise AssertionError("ISO-TP transfer did not settle")

    coordinator.pump = pump  # type: ignore[attr-defined]
    return coordinator, pad


def test_iso_tp_exchanges_multi_frame_opaque_payloads_over_simulated_can() -> None:
    coordinator, pad = _endpoints()
    coordinator.send(bytes(range(48)))
    coordinator.pump()  # type: ignore[attr-defined]
    assert pad.receive_payload() == bytes(range(48))

    pad.send(bytes(range(48)))
    coordinator.pump()  # type: ignore[attr-defined]
    assert coordinator.receive_payload() == bytes(range(48))


def test_iso_tp_latest_value_overwrites_pending_before_dispatch() -> None:
    coordinator, pad = _endpoints()
    coordinator.send(b"first")
    coordinator.send(b"second")  # overwrites before any poll; only second is transmitted
    coordinator.pump()  # type: ignore[attr-defined]
    assert pad.receive_payload() == b"second"
    assert pad.receive_payload() is None


def test_iso_tp_rejects_oversize_payload_and_ignores_other_frames() -> None:
    coordinator, _ = _endpoints()
    with pytest.raises(ValueError, match="256"):
        coordinator.send(b"x" * (BUTTON_PAD_TRANSPORT_MAXIMUM_PAYLOAD_LENGTH + 1))
    assert not coordinator.on_frame(CanFrame(0x123, b"\x00"))


def test_iso_tp_discards_bad_sequence_and_timed_out_partial_transfers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now_ns = 0
    monkeypatch.setattr(isotp.protocol.time, "perf_counter_ns", lambda: now_ns)
    receiver = IsoTpEndpoint(tx_id=0x709, rx_id=0x708, send_frame=lambda frame: None)
    assert receiver.on_frame(CanFrame(0x708, b"\x10\x08abcdef"))
    receiver.poll()
    assert receiver.on_frame(CanFrame(0x708, b"\x22gh"))
    receiver.poll()
    assert receiver.receive_payload() is None

    assert receiver.on_frame(CanFrame(0x708, b"\x10\x08abcdef"))
    receiver.poll()
    now_ns = 2_000_000_000
    receiver.poll()
    assert receiver.receive_payload() is None
