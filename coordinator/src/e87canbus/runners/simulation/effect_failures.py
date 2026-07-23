"""Mapping executor effect failures onto kernel failure inputs."""

from __future__ import annotations

from typing import assert_never

from e87canbus.adapters.output import (
    CanEffectFailure,
    EffectFailure,
    HighBeamActuatorFailure,
    SteeringActuatorFailure,
)
from e87canbus.config import CanNetwork
from e87canbus.kernel import CanEffectExecutionFailed, SteeringActuatorFailed

EffectFailureInput = CanEffectExecutionFailed | SteeringActuatorFailed


def effect_failure_input(
    failure: EffectFailure,
    failed_at: float,
) -> EffectFailureInput:
    match failure:
        case CanEffectFailure(network, message, origin_button_index):
            return CanEffectExecutionFailed(network, failed_at, message, origin_button_index)
        case SteeringActuatorFailure(message, origin_button_index):
            return SteeringActuatorFailed(failed_at, message, origin_button_index)
        case HighBeamActuatorFailure(message, origin_button_index):
            return CanEffectExecutionFailed(
                CanNetwork.KCAN,
                failed_at,
                message,
                origin_button_index,
            )
        case _:
            assert_never(failure)
