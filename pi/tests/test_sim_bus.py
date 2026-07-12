from e87canbus.can_io import CanFrame
from e87canbus.sim_bus import InMemoryCanNetwork


def test_sending_delivers_to_other_bus() -> None:
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    neotrellis_bus = network.create_bus("neotrellis")
    frame = CanFrame(0x700, b"\x00\x01")

    pi_bus.send(frame)

    assert neotrellis_bus.receive(timeout_s=0.01) == frame


def test_sender_does_not_receive_own_frame() -> None:
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    network.create_bus("neotrellis")

    pi_bus.send(CanFrame(0x700, b"\x00\x01"))

    assert pi_bus.receive(timeout_s=0.01) is None


def test_multiple_receivers_each_receive_a_copy() -> None:
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    neotrellis_bus = network.create_bus("neotrellis")
    logger_bus = network.create_bus("logger")
    frame = CanFrame(0x700, b"\x02\x01")

    pi_bus.send(frame)

    assert neotrellis_bus.receive(timeout_s=0) == frame
    assert logger_bus.receive(timeout_s=0) == frame


def test_receive_returns_none_when_no_frame_is_queued() -> None:
    network = InMemoryCanNetwork()
    bus = network.create_bus("pi")

    assert bus.receive(timeout_s=5.0) is None


def test_trace_records_source_frame_and_timestamp() -> None:
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    network.create_bus("neotrellis")
    frame = CanFrame(0x700, b"\x00\x01")

    pi_bus.send(frame)

    trace = network.trace()
    assert len(trace) == 1
    assert trace[0].source == "pi"
    assert trace[0].frame == frame
    assert trace[0].monotonic_s > 0

    network.clear_trace()

    assert network.trace() == ()


def test_create_bus_rejects_duplicate_name() -> None:
    network = InMemoryCanNetwork()
    network.create_bus("pi")

    try:
        network.create_bus("pi")
    except ValueError as exc:
        assert "bus already exists" in str(exc)
    else:
        raise AssertionError("expected duplicate bus name to be rejected")
