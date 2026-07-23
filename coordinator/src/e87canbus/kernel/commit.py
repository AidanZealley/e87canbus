"""The kernel's output contract: commits, projection topics and their diff.

A ``Commit`` is returned only after controller state is mutated. Its
``changed_topics`` is a closed set derived purely from projection differences,
so publication never depends on a runtime-registered event bus.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from e87canbus.application.controller import ApplicationSnapshot
from e87canbus.kernel.health import RuntimeHealth
from e87canbus.output import EffectRequest


class StateTopic(StrEnum):
    """Closed service projection topics; not a runtime-extensible event bus."""

    VEHICLE = "vehicle"
    ENGINE = "engine"
    STEERING = "steering"
    BUTTONS = "buttons"
    LIGHTING = "lighting"
    DEVICES = "devices"
    HEALTH = "health"


INITIAL_KERNEL_TOPICS = frozenset(
    {
        StateTopic.VEHICLE,
        StateTopic.ENGINE,
        StateTopic.STEERING,
        StateTopic.BUTTONS,
        StateTopic.LIGHTING,
        StateTopic.HEALTH,
        StateTopic.DEVICES,
    }
)


class KernelLifecycle(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"


@dataclass(frozen=True)
class Commit:
    """One accepted transition after state mutation, with ordered desired effects.

    ``snapshot`` is the complete immutable application projection. Button output is derived from
    that application state and emitted atomically; adapter-owned device observations and immutable
    runtime diagnostics remain separate service projections rather than duplicate application
    state.
    """

    revision: int
    snapshot: ApplicationSnapshot
    effects: tuple[EffectRequest, ...]
    changed_topics: frozenset[StateTopic]
    state_changed: bool


@dataclass(frozen=True)
class DiagnosticSnapshot:
    lifecycle: KernelLifecycle
    revision: int
    health: RuntimeHealth


def changed_controller_topics(
    previous: ApplicationSnapshot,
    current: ApplicationSnapshot,
    *,
    buttons_changed: bool,
    health_changed: bool,
) -> frozenset[StateTopic]:
    """Compare fixed projections without introducing string dispatch or registration."""

    changed: set[StateTopic] = set()
    if (
        current.vehicle_speed_kph != previous.vehicle_speed_kph
        or current.speed_valid != previous.speed_valid
    ):
        changed.add(StateTopic.VEHICLE)
    if current.engine != previous.engine:
        changed.add(StateTopic.ENGINE)
    if (
        current.steering_mode != previous.steering_mode
        or current.manual_assistance_level != previous.manual_assistance_level
        or current.maximum_assistance_active != previous.maximum_assistance_active
        or current.active_steering_curve != previous.active_steering_curve
        or (current.steering_curve_activation_status != previous.steering_curve_activation_status)
    ):
        changed.add(StateTopic.STEERING)
    if buttons_changed:
        changed.add(StateTopic.BUTTONS)
    if (
        current.high_beam_enabled != previous.high_beam_enabled
        or current.high_beam_strobe_active != previous.high_beam_strobe_active
        or (current.high_beam_strobe_cycles_remaining != previous.high_beam_strobe_cycles_remaining)
    ):
        changed.add(StateTopic.LIGHTING)
    if health_changed:
        changed.add(StateTopic.HEALTH)
    return frozenset(changed)
