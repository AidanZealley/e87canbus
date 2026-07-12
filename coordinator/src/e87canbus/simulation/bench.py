"""Run the bench ping-pong app against simulated CAN devices."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from e87canbus.cli.bench_pingpong import handle_frame
from e87canbus.config import CustomCanIds
from e87canbus.protocol.can import decode_button_event
from e87canbus.simulation.bus import InMemoryCanNetwork
from e87canbus.simulation.devices import SimulatedNeoTrellisNode

LOGGER = logging.getLogger(__name__)


def run_simulated_bench(cycles: int, button_index: int, ids: CustomCanIds) -> None:
    network = InMemoryCanNetwork()
    pi_bus = network.create_bus("pi")
    neotrellis = SimulatedNeoTrellisNode(
        bus=network.create_bus("neotrellis"),
        ids=ids,
        button_index=button_index,
    )

    for _ in range(cycles):
        sent = neotrellis.send_next_button_event()
        event = decode_button_event(sent, ids)
        if event is not None:
            LOGGER.info(
                "sim neotrellis sent button event: index=%d pressed=%s",
                event.button_index,
                event.pressed,
            )

        frame = pi_bus.receive(timeout_s=0)
        if frame is not None:
            handle_frame(pi_bus, frame, ids)

        for update in neotrellis.process_pending_led_updates():
            LOGGER.info(
                "sim neotrellis received led update: index=%d colour=%d",
                update.button_index,
                update.colour_code,
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the E87 bench app in simulation.")
    parser.add_argument("--cycles", type=int, default=4, help="Number of button events to send.")
    parser.add_argument("--button-index", type=int, default=0, help="Simulated button index.")
    parser.add_argument("--log-level", default="INFO")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.cycles < 1:
        LOGGER.error("--cycles must be at least 1")
        return 2
    if not 0 <= args.button_index <= 255:
        LOGGER.error("--button-index must be between 0 and 255")
        return 2

    run_simulated_bench(args.cycles, args.button_index, CustomCanIds())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
