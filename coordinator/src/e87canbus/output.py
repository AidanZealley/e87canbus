"""Capability-based application effect execution and final CAN rate policy."""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, assert_never

from e87canbus.application.events import (
    ApplicationEffect,
    SetButtonLeds,
    SetSteeringAssistance,
)
from e87canbus.can_io import CanTransmitter
from e87canbus.config import CanNetwork, TxPolicyConfig
from e87canbus.protocol.can import CanFrame
from e87canbus.protocol.router import ProtocolRouter

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CanEffectFailure:
    network: CanNetwork
    message: str


@dataclass(frozen=True)
class SteeringActuatorFailure:
    message: str


EffectFailure = CanEffectFailure | SteeringActuatorFailure


@dataclass(frozen=True)
class EffectExecutionDiagnostics:
    """Process-lifetime effect outcome counters; no effect detail is retained."""

    sent: tuple[tuple[CanNetwork, int], ...]
    dropped: tuple[tuple[CanNetwork, int], ...]
    rate_limited: tuple[tuple[CanNetwork, int], ...]
    failed: tuple[tuple[CanNetwork, int], ...]
    steering_sent: int
    steering_dropped: int
    steering_failed: int


EMPTY_EFFECT_DIAGNOSTICS = EffectExecutionDiagnostics(
    sent=tuple((network, 0) for network in CanNetwork),
    dropped=tuple((network, 0) for network in CanNetwork),
    rate_limited=tuple((network, 0) for network in CanNetwork),
    failed=tuple((network, 0) for network in CanNetwork),
    steering_sent=0,
    steering_dropped=0,
    steering_failed=0,
)


def add_effect_diagnostics(
    first: EffectExecutionDiagnostics,
    second: EffectExecutionDiagnostics,
) -> EffectExecutionDiagnostics:
    def summed(
        left: tuple[tuple[CanNetwork, int], ...],
        right: tuple[tuple[CanNetwork, int], ...],
    ) -> tuple[tuple[CanNetwork, int], ...]:
        left_by_network = dict(left)
        right_by_network = dict(right)
        return tuple(
            (network, left_by_network.get(network, 0) + right_by_network.get(network, 0))
            for network in CanNetwork
        )

    return EffectExecutionDiagnostics(
        sent=summed(first.sent, second.sent),
        dropped=summed(first.dropped, second.dropped),
        rate_limited=summed(first.rate_limited, second.rate_limited),
        failed=summed(first.failed, second.failed),
        steering_sent=first.steering_sent + second.steering_sent,
        steering_dropped=first.steering_dropped + second.steering_dropped,
        steering_failed=first.steering_failed + second.steering_failed,
    )


class SteeringActuator(Protocol):
    def set_assistance(self, command: SetSteeringAssistance) -> None:
        """Apply one already-selected, dimensionless assistance command."""


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

    def send(self, frame: CanFrame) -> bool:
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
            return False

        # Reserve the budget before I/O: a failed send has an uncertain bus outcome and must
        # not permit an unbounded retry loop.
        self._network_send_times.append(now)
        self._transmitter.send(frame)
        return True


class EffectExecutor:
    """Route and execute ordered effects using only explicitly granted capabilities."""

    def __init__(
        self,
        transmitters: Mapping[CanNetwork, SafeCanTransmitter] | None = None,
        router: ProtocolRouter | None = None,
        steering_actuator: SteeringActuator | None = None,
    ) -> None:
        self._transmitters = dict(transmitters or {})
        self._router = router or ProtocolRouter()
        self._steering_actuator = steering_actuator
        self._sent = {network: 0 for network in CanNetwork}
        self._dropped = {network: 0 for network in CanNetwork}
        self._rate_limited = {network: 0 for network in CanNetwork}
        self._failed = {network: 0 for network in CanNetwork}
        self._steering_sent = 0
        self._steering_dropped = 0
        self._steering_failed = 0

    @property
    def diagnostics(self) -> EffectExecutionDiagnostics:
        return EffectExecutionDiagnostics(
            sent=tuple(self._sent.items()),
            dropped=tuple(self._dropped.items()),
            rate_limited=tuple(self._rate_limited.items()),
            failed=tuple(self._failed.items()),
            steering_sent=self._steering_sent,
            steering_dropped=self._steering_dropped,
            steering_failed=self._steering_failed,
        )

    def execute(self, effects: tuple[ApplicationEffect, ...]) -> tuple[EffectFailure, ...]:
        failures: list[EffectFailure] = []
        for effect in effects:
            match effect:
                case SetSteeringAssistance():
                    steering_failure = self._execute_steering(effect)
                    if steering_failure is not None:
                        failures.append(steering_failure)
                case SetButtonLeds():
                    can_failure = self._execute_can(effect)
                    if can_failure is not None:
                        failures.append(can_failure)
                case _:
                    assert_never(effect)
        return tuple(failures)

    def _execute_can(self, effect: SetButtonLeds) -> CanEffectFailure | None:
        routed = self._router.encode(effect)
        transmitter = self._transmitters.get(routed.network)
        if transmitter is None:
            LOGGER.warning(
                "dropped effect for unavailable TX capability: network=%s id=0x%03x",
                routed.network.value,
                routed.frame.arbitration_id,
            )
            self._dropped[routed.network] += 1
            return None
        try:
            sent = transmitter.send(routed.frame)
        except (OSError, RuntimeError) as exc:
            LOGGER.warning(
                "failed to execute effect: network=%s id=0x%03x error=%s",
                routed.network.value,
                routed.frame.arbitration_id,
                exc,
            )
            self._failed[routed.network] += 1
            return CanEffectFailure(routed.network, str(exc))
        if sent:
            self._sent[routed.network] += 1
        else:
            self._rate_limited[routed.network] += 1
        return None

    def _execute_steering(
        self,
        command: SetSteeringAssistance,
    ) -> SteeringActuatorFailure | None:
        if self._steering_actuator is None:
            self._steering_dropped += 1
            return None
        try:
            self._steering_actuator.set_assistance(command)
        except (OSError, RuntimeError) as exc:
            LOGGER.warning("failed to execute steering effect: error=%s", exc)
            self._steering_failed += 1
            return SteeringActuatorFailure(str(exc))
        self._steering_sent += 1
        return None


def _discard_expired(send_times: deque[float], cutoff: float) -> None:
    while send_times and send_times[0] <= cutoff:
        send_times.popleft()
