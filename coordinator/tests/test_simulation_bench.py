from e87canbus.cli.bench_pingpong import handle_frame
from e87canbus.config import CanNetwork, CustomCanIds, TxPolicyConfig
from e87canbus.output import EffectExecutor, SafeCanTransmitter
from e87canbus.protocol.can import LED_GREEN, LED_OFF
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.simulation.bench import run_simulated_bench
from e87canbus.simulation.bus import InMemoryCanNetwork
from e87canbus.simulation.devices import SimulatedNeoTrellisNode


def executor_for(pi_bus, ids: CustomCanIds) -> EffectExecutor:
    router = ProtocolRouter(ids)
    return EffectExecutor(
        {
            CanNetwork.KCAN: SafeCanTransmitter(
                pi_bus,
                TxPolicyConfig(max_frames_per_network_window=1_000),
            )
        },
        router,
    )


def run_one_cycle(
    node: SimulatedNeoTrellisNode,
    pi_bus,
    executor: EffectExecutor,
    ids: CustomCanIds,
) -> None:
    node.send_next_button_event()
    frame = pi_bus.receive(timeout_s=0)
    assert frame is not None
    handle_frame(executor, frame, ids)
    node.process_pending_led_updates()


def test_pressed_event_causes_green_led_update() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)

    run_one_cycle(node, pi_bus, executor_for(pi_bus, ids), ids)

    assert node.led_colours == {0: LED_GREEN}


def test_released_event_causes_off_led_update() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)
    executor = executor_for(pi_bus, ids)

    run_one_cycle(node, pi_bus, executor, ids)
    run_one_cycle(node, pi_bus, executor, ids)

    assert node.led_colours == {0: LED_OFF}


def test_four_cycles_alternate_green_and_off() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)
    executor = executor_for(pi_bus, ids)
    colours: list[int] = []

    for _ in range(4):
        run_one_cycle(node, pi_bus, executor, ids)
        colours.append(node.led_colours[0])

    assert colours == [LED_GREEN, LED_OFF, LED_GREEN, LED_OFF]


def test_simulated_bench_cli_flow_runs_expected_cycles(caplog) -> None:
    run_simulated_bench(cycles=2, button_index=4, ids=CustomCanIds())

    assert caplog.text == ""
