"""Mapping executor effect failures onto kernel failure inputs."""

from __future__ import annotations

from typing import assert_never

from e87canbus.adapters.output import (
    CanEffectFailure,
    EffectFailure,
    SteeringActuatorFailure,
)
from e87canbus.kernel import CanEffectExecutionFailed, SteeringActuatorFailed

EffectFailureInput = CanEffectExecutionFailed | SteeringActuatorFailed


def effect_failure_input(
    failure: EffectFailure,
    failed_at: float,
) -> EffectFailureInput:
    match failure:
        case CanEffectFailure(network, message):
            return CanEffectExecutionFailed(network, failed_at, message)
        case SteeringActuatorFailure(message):
            return SteeringActuatorFailed(failed_at, message)
        case _:
            assert_never(failure)
