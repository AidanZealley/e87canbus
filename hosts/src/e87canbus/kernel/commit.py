"""The kernel's output contract: commits, projection topics and their diff.

A ``Commit`` reports changed topics for an accepted input. Its
``changed_topics`` is a closed set derived from state comparisons, so
publication never depends on a runtime-registered event bus.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from e87canbus.domain.controller import ApplicationSnapshot
from e87canbus.kernel.health import RuntimeHealth


class StateTopic(StrEnum):
    """Closed service projection topics; not a runtime-extensible event bus."""

    VEHICLE = "vehicle"
    ENGINE = "engine"
    STEERING = "steering"
    BUTTONS = "buttons"
    HEALTH = "health"


INITIAL_KERNEL_TOPICS = frozenset(
    {
        StateTopic.VEHICLE,
        StateTopic.ENGINE,
        StateTopic.STEERING,
        StateTopic.BUTTONS,
        StateTopic.HEALTH,
    }
)


class KernelLifecycle(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"


@dataclass(frozen=True)
class Commit:
    """Changed projections after one accepted input."""

    changed_topics: frozenset[StateTopic]


@dataclass(frozen=True)
class DiagnosticSnapshot:
    lifecycle: KernelLifecycle
    health: RuntimeHealth


def changed_controller_topics(
    previous: ApplicationSnapshot,
    current: ApplicationSnapshot,
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
    ):
        changed.add(StateTopic.STEERING)
    if (
        current.active_button_profile_id != previous.active_button_profile_id
        or current.active_button_profile_revision != previous.active_button_profile_revision
    ):
        changed.add(StateTopic.BUTTONS)
    return frozenset(changed)
