"""Bench CAN ping-pong app for Pi-to-Arduino validation."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.config import CustomCanIds
from e87canbus.protocol.can import (
    LED_GREEN,
    LED_OFF,
    CanBus,
    CanFrame,
    LedUpdatePayload,
    decode_button_event,
    encode_led_update,
)

LOGGER = logging.getLogger(__name__)


def led_update_for_button_event(frame: CanFrame, ids: CustomCanIds) -> CanFrame | None:
    event = decode_button_event(frame, ids)
    if event is None:
        return None

    colour = LED_GREEN if event.pressed else LED_OFF
    return encode_led_update(LedUpdatePayload(event.button_index, colour), ids)


def handle_frame(bus: CanBus, frame: CanFrame, ids: CustomCanIds) -> None:
    try:
        reply = led_update_for_button_event(frame, ids)
    except ValueError as exc:
        LOGGER.warning(
            "malformed button event frame: id=0x%03x data=%s error=%s",
            frame.arbitration_id,
            frame.data.hex(),
            exc,
        )
        return

    if reply is None:
        LOGGER.debug("ignored frame: id=0x%03x data=%s", frame.arbitration_id, frame.data.hex())
        return

    event = decode_button_event(frame, ids)
    if event is None:
        return

    LOGGER.info("received button event: index=%d pressed=%s", event.button_index, event.pressed)
    bus.send(reply)
    colour_name = "green" if reply.data[1] == LED_GREEN else "off"
    LOGGER.info("sent led update: index=%d colour=%s", reply.data[0], colour_name)


def run_pingpong(bus: CanBus, ids: CustomCanIds, receive_timeout_s: float = 1.0) -> None:
    while True:
        frame = bus.receive(timeout_s=receive_timeout_s)
        if frame is None:
            continue
        handle_frame(bus, frame, ids)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the E87 bench CAN ping-pong app.")
    parser.add_argument("--interface", default="can0", help="SocketCAN interface to open.")
    parser.add_argument("--receive-timeout-s", type=float, default=1.0)
    parser.add_argument("--log-level", default="INFO")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    ids = CustomCanIds()
    try:
        with SocketCanBus(args.interface) as bus:
            LOGGER.info("opened SocketCAN interface %s", args.interface)
            run_pingpong(bus, ids, args.receive_timeout_s)
    except KeyboardInterrupt:
        LOGGER.info("stopping bench ping-pong")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
