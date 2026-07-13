"""Transport-neutral coordinator runtime shared by simulated and live runners."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from e87canbus.application.controller import ApplicationController, ApplicationOutput
from e87canbus.config import CanNetwork
from e87canbus.protocol.can import CanBus, CanFrame, RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReceivedCanFrame:
    """A CAN frame paired with its network and ingress observation time."""

    network: CanNetwork
    frame: CanFrame
    received_at: float


def _empty_can_health() -> dict[CanNetwork, float | None]:
    return {network: None for network in CanNetwork}


@dataclass
class RuntimeHealth:
    latest_rx_monotonic_s: dict[CanNetwork, float | None] = field(
        default_factory=_empty_can_health
    )

    def record_receive(self, network: CanNetwork, monotonic_s: float) -> None:
        self.latest_rx_monotonic_s[network] = monotonic_s


class CoordinatorRuntime:
    """Process one received frame at a time and dispatch application outputs."""

    def __init__(
        self,
        buses: Mapping[CanNetwork, CanBus],
        application: ApplicationController | None = None,
        router: ProtocolRouter | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        tx_networks: frozenset[CanNetwork] = frozenset(),
    ) -> None:
        self.buses = dict(buses)
        self.application = application or ApplicationController()
        self.router = router or ProtocolRouter()
        self.health = RuntimeHealth()
        self._monotonic = monotonic
        self._tx_networks = tx_networks

    def start(self) -> None:
        """Synchronize the application's authoritative output state."""

        self._send_outputs(self.application.desired_outputs())

    def process_frame(self, received: ReceivedCanFrame) -> None:
        """Process a received input while isolating malformed traffic and output failures."""

        routed = RoutedCanFrame(network=received.network, frame=received.frame)
        self.health.record_receive(received.network, received.received_at)
        try:
            event = self.router.decode(routed)
        except ValueError as exc:
            LOGGER.warning(
                "ignored malformed recognized frame: network=%s id=0x%03x data=%s error=%s",
                routed.network.value,
                routed.frame.arbitration_id,
                routed.frame.data.hex(),
                exc,
            )
            return

        if event is None:
            return
        self._send_outputs(self.application.handle_event(event, received.received_at))

    def tick(self) -> None:
        self._send_outputs(self.application.tick(self._monotonic()))

    def drain_pending(self) -> int:
        """Drain endpoint queues in stable round-robin network order."""

        processed = 0
        ordered_networks = tuple(network for network in CanNetwork if network in self.buses)
        while True:
            found_frame = False
            for network in ordered_networks:
                frame = self.buses[network].receive(timeout_s=0)
                if frame is None:
                    continue
                found_frame = True
                processed += 1
                self.process_frame(
                    ReceivedCanFrame(
                        network=network,
                        frame=frame,
                        received_at=self._monotonic(),
                    )
                )
            if not found_frame:
                return processed

    def _send_outputs(self, outputs: tuple[ApplicationOutput, ...]) -> None:
        for output in outputs:
            try:
                routed = self.router.encode(output)
            except ValueError as exc:
                LOGGER.warning("ignored unencodable application output: %s", exc)
                continue

            if routed.network not in self._tx_networks:
                LOGGER.warning(
                    "dropped output for tx-disabled network: network=%s id=0x%03x",
                    routed.network.value,
                    routed.frame.arbitration_id,
                )
                continue

            bus = self.buses.get(routed.network)
            if bus is None:
                LOGGER.warning(
                    "ignored output for unavailable CAN network: network=%s id=0x%03x",
                    routed.network.value,
                    routed.frame.arbitration_id,
                )
                continue
            try:
                bus.send(routed.frame)
            except (OSError, RuntimeError) as exc:
                LOGGER.warning(
                    "failed to send output and continued: network=%s id=0x%03x error=%s",
                    routed.network.value,
                    routed.frame.arbitration_id,
                    exc,
                )
