"""Bench CAN ping-pong app for Pi-to-Arduino validation."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.application.events import (
    BUTTON_LED_COUNT,
    OFF_BUTTON_LEDS,
    ButtonLedState,
    LedColour,
    SetButtonLeds,
)
from e87canbus.can_io import CanReceiver
from e87canbus.config import CanNetwork, CustomCanIds, TxPolicyConfig
from e87canbus.output import EffectExecutor, SafeCanTransmitter
from e87canbus.protocol.can import CanFrame, decode_button_event
from e87canbus.protocol.router import ProtocolRouter

LOGGER = logging.getLogger(__name__)


def led_effect_for_button_event(
    frame: CanFrame,
    ids: CustomCanIds,
    state: ButtonLedState,
) -> SetButtonLeds | None:
    event = decode_button_event(frame, ids)
    if event is None:
        return None
    if not 0 <= event.button_index < BUTTON_LED_COUNT:
        raise ValueError(f"button_index must be between 0 and {BUTTON_LED_COUNT - 1}")
    colour = LedColour.GREEN if event.pressed else LedColour.OFF
    return SetButtonLeds(
        ButtonLedState(
            tuple(
                colour if index == event.button_index else current
                for index, current in enumerate(state.colours)
            )
        )
    )


def handle_frame(
    executor: EffectExecutor,
    frame: CanFrame,
    ids: CustomCanIds,
    state: ButtonLedState,
) -> ButtonLedState:
    try:
        effect = led_effect_for_button_event(frame, ids, state)
    except ValueError as exc:
        LOGGER.warning(
            "malformed button event frame: id=0x%03x data=%s error=%s",
            frame.arbitration_id,
            frame.data.hex(),
            exc,
        )
        return state

    if effect is None:
        LOGGER.debug("ignored frame: id=0x%03x data=%s", frame.arbitration_id, frame.data.hex())
        return state

    executor.execute((effect,))
    LOGGER.info(
        "sent complete LED snapshot: colours=%s",
        ",".join(colour.value for colour in effect.colours.colours),
    )
    return effect.colours


def run_pingpong(
    receiver: CanReceiver,
    executor: EffectExecutor,
    ids: CustomCanIds,
    receive_timeout_s: float = 1.0,
) -> None:
    state = OFF_BUTTON_LEDS
    while True:
        frame = receiver.receive(timeout_s=receive_timeout_s)
        if frame is None:
            continue
        state = handle_frame(executor, frame, ids, state)


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
            router = ProtocolRouter(ids)
            executor = EffectExecutor(
                {
                    CanNetwork.KCAN: SafeCanTransmitter(
                        bus,
                        TxPolicyConfig(),
                    )
                },
                router,
            )
            run_pingpong(bus, executor, ids, args.receive_timeout_s)
    except KeyboardInterrupt:
        LOGGER.info("stopping bench ping-pong")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
