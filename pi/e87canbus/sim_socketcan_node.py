"""Simulated NeoTrellis node backed by a real SocketCAN interface."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from e87canbus.can_io import (
    ArduinoButtonEventPayload,
    decode_led_update,
    encode_button_event,
)
from e87canbus.config import CustomCanIds
from e87canbus.socketcan import SocketCanBus

LOGGER = logging.getLogger(__name__)


def run_socketcan_neotrellis(
    interface: str,
    cycles: int,
    button_index: int,
    ids: CustomCanIds,
    receive_timeout_s: float,
) -> None:
    next_pressed = True
    with SocketCanBus(interface) as bus:
        LOGGER.info("opened SocketCAN interface %s", interface)
        for _ in range(cycles):
            frame = encode_button_event(
                ArduinoButtonEventPayload(button_index=button_index, pressed=next_pressed),
                ids,
            )
            bus.send(frame)
            LOGGER.info(
                "sim neotrellis sent button event: index=%d pressed=%s",
                button_index,
                next_pressed,
            )
            next_pressed = not next_pressed

            reply = bus.receive(timeout_s=receive_timeout_s)
            if reply is None:
                LOGGER.warning("timed out waiting for led update")
                continue

            try:
                update = decode_led_update(reply, ids)
            except ValueError as exc:
                LOGGER.warning(
                    "sim neotrellis ignored malformed led update: id=0x%03x data=%s error=%s",
                    reply.arbitration_id,
                    reply.data.hex(),
                    exc,
                )
                continue

            if update is None:
                LOGGER.debug(
                    "sim neotrellis ignored frame: id=0x%03x data=%s",
                    reply.arbitration_id,
                    reply.data.hex(),
                )
                continue

            LOGGER.info(
                "sim neotrellis received led update: index=%d colour=%d",
                update.button_index,
                update.colour_code,
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a simulated NeoTrellis node on a SocketCAN interface.",
    )
    parser.add_argument("--interface", default="vcan0", help="SocketCAN interface to open.")
    parser.add_argument("--cycles", type=int, default=4, help="Number of button events to send.")
    parser.add_argument("--button-index", type=int, default=0, help="Simulated button index.")
    parser.add_argument("--receive-timeout-s", type=float, default=1.0)
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

    run_socketcan_neotrellis(
        interface=args.interface,
        cycles=args.cycles,
        button_index=args.button_index,
        ids=CustomCanIds(),
        receive_timeout_s=args.receive_timeout_s,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
