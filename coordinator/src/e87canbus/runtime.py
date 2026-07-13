"""Transport-neutral coordinator runtime shared by simulated and live runners."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from e87canbus.application.controller import (
    ApplicationSnapshot,
    initial_effects,
    normalize_state,
    snapshot,
    transition,
)
from e87canbus.application.events import ApplicationEvent, ControlTimerElapsed
from e87canbus.application.state import ApplicationState
from e87canbus.can_io import CanReceiver
from e87canbus.config import CanNetwork, SteeringConfig
from e87canbus.output import EffectExecutor
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
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
    """Decode, transition, commit, then execute one input at a time."""

    def __init__(
        self,
        receivers: Mapping[CanNetwork, CanReceiver],
        state: ApplicationState | None = None,
        steering_config: SteeringConfig | None = None,
        router: ProtocolRouter | None = None,
        executor: EffectExecutor | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.receivers = dict(receivers)
        self.steering_config = steering_config or SteeringConfig()
        self.state = normalize_state(state or ApplicationState(), self.steering_config)
        self.router = router or ProtocolRouter()
        self.executor = executor or EffectExecutor(router=self.router)
        self.health = RuntimeHealth()
        self._monotonic = monotonic

    def start(self) -> None:
        """Synchronize the verified output projection through the effect boundary."""

        self.executor.execute(initial_effects(self.state))

    def process_frame(self, received: ReceivedCanFrame) -> None:
        """Process a received input while isolating malformed traffic."""

        routed = RoutedCanFrame(network=received.network, frame=received.frame)
        self.health.record_receive(received.network, received.received_at)
        try:
            event = self.router.decode(routed, received.received_at)
        except ValueError as exc:
            LOGGER.warning(
                "ignored malformed recognized frame: network=%s id=0x%03x data=%s error=%s",
                routed.network.value,
                routed.frame.arbitration_id,
                routed.frame.data.hex(),
                exc,
            )
            return
        if event is not None:
            self._apply(event)

    def _apply(self, event: ApplicationEvent) -> None:
        result = transition(self.state, event, self.steering_config)
        self.state = result.state
        self.executor.execute(result.effects)

    def tick(self) -> None:
        self._apply(ControlTimerElapsed(self._monotonic()))

    def snapshot(self) -> ApplicationSnapshot:
        return snapshot(self.state, self.steering_config)

    def drain_pending(self) -> int:
        """Drain endpoint queues in stable round-robin network order."""

        processed = 0
        ordered_networks = tuple(
            network for network in CanNetwork if network in self.receivers
        )
        while True:
            found_frame = False
            for network in ordered_networks:
                frame = self.receivers[network].receive(timeout_s=0)
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
