"""The closed set of ordered inputs accepted by the coordinator kernel.

These are transport-independent: an input carries no FastAPI request, SSE
connection or simulator UI value. Adapters translate their own concerns into one of
these before submitting it through the single ``CoordinatorKernel.dispatch`` path.
"""

from __future__ import annotations

from dataclasses import dataclass

from e87canbus.config import CanNetwork
from e87canbus.domain.buttons.profiles import ActiveButtonProfile, validate_saved_profile_revision
from e87canbus.domain.events import ButtonPressed
from e87canbus.domain.intents import (
    OperatorIntent,
    is_operator_intent,
)
from e87canbus.domain.steering.curves import SteeringCurveDefinition
from e87canbus.protocol.can import CanFrame


@dataclass(frozen=True)
class KernelStarted:
    pass


@dataclass(frozen=True)
class ReceivedCanFrame:
    """A CAN frame paired with its network and ingress observation time."""

    network: CanNetwork
    frame: CanFrame
    received_at: float


@dataclass(frozen=True)
class TimerElapsed:
    now: float


@dataclass(frozen=True)
class CanReaderFailed:
    network: CanNetwork
    failed_at: float
    message: str


@dataclass(frozen=True)
class InboxOverflowed:
    network: CanNetwork | None
    failed_at: float
    message: str


@dataclass(frozen=True)
class ShutdownRequested:
    pass


@dataclass(frozen=True)
class ActivateSteeringCurve:
    definition: SteeringCurveDefinition
    saved_profile_id: str | None = None
    saved_profile_revision: int | None = None


@dataclass(frozen=True)
class ActivateButtonProfile:
    profile: ActiveButtonProfile
    saved_profile_revision: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.profile, ActiveButtonProfile):
            raise TypeError("profile must be a ActiveButtonProfile")
        validate_saved_profile_revision(self.saved_profile_revision)


@dataclass(frozen=True)
class ExecuteOperatorIntent:
    """A transport-independent operator intent submitted through a non-button adapter."""

    intent: OperatorIntent

    def __post_init__(self) -> None:
        if not is_operator_intent(self.intent):
            raise TypeError(f"unsupported operator intent: {type(self.intent).__name__}")


ControllerInput = (
    KernelStarted
    | ReceivedCanFrame
    | TimerElapsed
    | ButtonPressed
    | CanReaderFailed
    | InboxOverflowed
    | ShutdownRequested
    | ActivateSteeringCurve
    | ActivateButtonProfile
    | ExecuteOperatorIntent
)
