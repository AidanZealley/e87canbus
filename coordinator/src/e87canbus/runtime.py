"""Transport-neutral coordinator runtime shared by simulated and future live runners."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping

from e87canbus.application.controller import ApplicationController, ApplicationOutput
from e87canbus.config import CanNetwork
from e87canbus.protocol.can import CanBus, RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter

LOGGER = logging.getLogger(__name__)


class CoordinatorRuntime:
    """Process one routed frame at a time and dispatch application outputs."""

    def __init__(
        self,
        buses: Mapping[CanNetwork, CanBus],
        application: ApplicationController | None = None,
        router: ProtocolRouter | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.buses = dict(buses)
        self.application = application or ApplicationController()
        self.router = router or ProtocolRouter()
        self._monotonic = monotonic

    def start(self) -> None:
        """Synchronize the application's authoritative output state."""

        self._send_outputs(self.application.desired_outputs())

    def process_frame(self, routed: RoutedCanFrame) -> None:
        """Process a routed input while isolating malformed traffic and output failures."""

        self.application.state.can_health.record_receive(routed.network, self._monotonic())
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
        self._send_outputs(self.application.handle_event(event))

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
                self.process_frame(RoutedCanFrame(network=network, frame=frame))
            if not found_frame:
                return processed

    def _send_outputs(self, outputs: tuple[ApplicationOutput, ...]) -> None:
        for output in outputs:
            try:
                routed = self.router.encode(output)
            except ValueError as exc:
                LOGGER.warning("ignored unencodable application output: %s", exc)
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
