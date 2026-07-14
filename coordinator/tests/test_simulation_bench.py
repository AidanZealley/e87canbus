from e87canbus.application.events import OFF_BUTTON_LEDS, ButtonLedState
from e87canbus.cli.bench_pingpong import handle_frame
from e87canbus.config import CanNetwork, CustomCanIds, TxPolicyConfig
from e87canbus.output import EffectExecutor, SafeCanTransmitter
from e87canbus.protocol.generated import LED_COLOUR_GREEN, LED_COLOUR_OFF
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
    state: ButtonLedState = OFF_BUTTON_LEDS,
) -> ButtonLedState:
    node.send_next_button_event()
    frame = pi_bus.receive(timeout_s=0)
    assert frame is not None
    state = handle_frame(executor, frame, ids, state)
    node.process_pending_led_snapshots()
    return state


def test_pressed_event_causes_green_led_snapshot() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)

    run_one_cycle(node, pi_bus, executor_for(pi_bus, ids), ids)

    assert node.led_colours == (LED_COLOUR_GREEN,) + (LED_COLOUR_OFF,) * 15


def test_released_event_causes_off_led_snapshot() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)
    executor = executor_for(pi_bus, ids)

    state = run_one_cycle(node, pi_bus, executor, ids)
    run_one_cycle(node, pi_bus, executor, ids, state)

    assert node.led_colours == (LED_COLOUR_OFF,) * 16


def test_four_cycles_alternate_green_and_off() -> None:
    ids = CustomCanIds()
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    node = SimulatedNeoTrellisNode(bus=network.create_bus("neotrellis"), ids=ids)
    executor = executor_for(pi_bus, ids)
    colours: list[int] = []

    state = OFF_BUTTON_LEDS
    for _ in range(4):
        state = run_one_cycle(node, pi_bus, executor, ids, state)
        colours.append(node.led_colours[0])

    assert colours == [
        LED_COLOUR_GREEN,
        LED_COLOUR_OFF,
        LED_COLOUR_GREEN,
        LED_COLOUR_OFF,
    ]


def test_simulated_bench_cli_flow_runs_expected_cycles(caplog) -> None:
    run_simulated_bench(cycles=2, button_index=4, ids=CustomCanIds())

    assert caplog.text == ""
