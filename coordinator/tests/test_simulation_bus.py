from e87canbus.config import CanNetwork
from e87canbus.protocol.can import CanFrame
from e87canbus.simulation.bus import InMemoryCanNetwork, InMemoryCanTopology


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


def test_topology_keeps_networks_isolated_and_allows_same_node_name() -> None:
    topology = InMemoryCanTopology()
    kcan_pi = topology.create_bus(CanNetwork.KCAN, "pi")
    kcan_peer = topology.create_bus(CanNetwork.KCAN, "peer")
    ptcan_pi = topology.create_bus(CanNetwork.PTCAN, "pi")
    ptcan_peer = topology.create_bus(CanNetwork.PTCAN, "peer")
    frame = CanFrame(0x321, b"\xaa")

    kcan_pi.send(frame)

    assert kcan_peer.receive(timeout_s=0) == frame
    assert ptcan_pi.receive(timeout_s=0) is None
    assert ptcan_peer.receive(timeout_s=0) is None


def test_topology_trace_is_globally_ordered_across_networks() -> None:
    topology = InMemoryCanTopology()
    ptcan = topology.create_bus(CanNetwork.PTCAN, "simulated-car")
    kcan = topology.create_bus(CanNetwork.KCAN, "neotrellis")
    fcan = topology.create_bus(CanNetwork.FCAN, "simulated-car")

    ptcan.send(CanFrame(0x100, b"\x01"))
    kcan.send(CanFrame(0x101, b"\x02"))
    fcan.send(CanFrame(0x102, b"\x03"))

    trace = topology.trace()
    assert [entry.sequence for entry in trace] == [1, 2, 3]
    assert [entry.network for entry in trace] == [
        CanNetwork.PTCAN,
        CanNetwork.KCAN,
        CanNetwork.FCAN,
    ]
    assert list(trace) == sorted(trace, key=lambda entry: entry.monotonic_s)


def test_topology_owned_network_does_not_duplicate_trace_storage() -> None:
    topology = InMemoryCanTopology()
    kcan = topology.create_bus(CanNetwork.KCAN, "pi")

    kcan.send(CanFrame(0x100, b""))

    assert len(topology.trace()) == 1
    assert topology.network(CanNetwork.KCAN).trace() == ()


def test_topology_uses_one_global_ring_buffer_and_clear_resets_sequence() -> None:
    topology = InMemoryCanTopology(trace_capacity=2)
    kcan = topology.create_bus(CanNetwork.KCAN, "pi")
    ptcan = topology.create_bus(CanNetwork.PTCAN, "pi")

    kcan.send(CanFrame(0x100, b""))
    ptcan.send(CanFrame(0x101, b""))
    kcan.send(CanFrame(0x102, b""))

    assert [entry.sequence for entry in topology.trace()] == [2, 3]

    topology.clear_trace()
    ptcan.send(CanFrame(0x103, b""))

    assert [entry.sequence for entry in topology.trace()] == [1]
