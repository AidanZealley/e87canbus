"""Capability-based application effect execution and final CAN rate policy."""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable, Mapping

from e87canbus.application.events import ApplicationEffect
from e87canbus.can_io import CanTransmitter
from e87canbus.config import CanNetwork, TxPolicyConfig
from e87canbus.protocol.can import CanFrame
from e87canbus.protocol.router import ProtocolRouter

LOGGER = logging.getLogger(__name__)


class SafeCanTransmitter:
    """The only coordinator CAN write capability, enforcing the network window."""

    def __init__(
        self,
        transmitter: CanTransmitter,
        policy: TxPolicyConfig,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transmitter = transmitter
        self._policy = policy
        self._clock = clock
        self._network_send_times: deque[float] = deque()

    def send(self, frame: CanFrame) -> None:
        now = self._clock()
        _discard_expired(
            self._network_send_times,
            now - self._policy.network_window_s,
        )
        if len(self._network_send_times) >= self._policy.max_frames_per_network_window:
            LOGGER.warning(
                "dropped rate-limited CAN frame: id=0x%03x reason=network-window",
                frame.arbitration_id,
            )
            return

        # Reserve the budget before I/O: a failed send has an uncertain bus outcome and must
        # not permit an unbounded retry loop.
        self._network_send_times.append(now)
        self._transmitter.send(frame)


class EffectExecutor:
    """Route and execute ordered effects using only explicitly granted capabilities."""

    def __init__(
        self,
        transmitters: Mapping[CanNetwork, SafeCanTransmitter] | None = None,
        router: ProtocolRouter | None = None,
    ) -> None:
        self._transmitters = dict(transmitters or {})
        self._router = router or ProtocolRouter()

    def execute(self, effects: tuple[ApplicationEffect, ...]) -> None:
        for effect in effects:
            routed = self._router.encode(effect)
            transmitter = self._transmitters.get(routed.network)
            if transmitter is None:
                LOGGER.warning(
                    "dropped effect for unavailable TX capability: network=%s id=0x%03x",
                    routed.network.value,
                    routed.frame.arbitration_id,
                )
                continue
            try:
                transmitter.send(routed.frame)
            except (OSError, RuntimeError) as exc:
                LOGGER.warning(
                    "failed to execute effect and continued: network=%s id=0x%03x error=%s",
                    routed.network.value,
                    routed.frame.arbitration_id,
                    exc,
                )


def _discard_expired(send_times: deque[float], cutoff: float) -> None:
    while send_times and send_times[0] <= cutoff:
        send_times.popleft()
