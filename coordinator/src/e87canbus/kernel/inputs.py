"""The closed set of timed inputs accepted by the coordinator kernel.

These are transport-independent: an input carries no FastAPI request, Socket.IO
session or simulator UI value. Adapters translate their own concerns into one of
these before submitting it through the single ``CoordinatorKernel.dispatch`` path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from e87canbus.application.events import (
    ButtonFeedbackDeadlineReached,
    HighBeamStrobeDeadlineReached,
)
from e87canbus.application.intents import (
    DEFAULT_OPERATOR_INTENT_CONTEXT,
    OperatorIntent,
    OperatorIntentContext,
    is_operator_intent,
)
from e87canbus.config import CanNetwork
from e87canbus.device import DeviceRole
from e87canbus.features.steering import SteeringCurveDefinition
from e87canbus.protocol.can import CanFrame
from e87canbus.protocol.servotronic_protocol import ServotronicStatus


@dataclass(frozen=True)
class KernelStarted:
    now: float


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
class CanEffectExecutionFailed:
    network: CanNetwork
    failed_at: float
    message: str
    origin_button_index: int | None = None


@dataclass(frozen=True)
class SteeringActuatorFailed:
    failed_at: float
    message: str
    origin_button_index: int | None = None


@dataclass(frozen=True)
class InboxOverflowed:
    network: CanNetwork | None
    failed_at: float
    message: str


@dataclass(frozen=True)
class DeviceAdapterFailed:
    role: DeviceRole
    failed_at: float
    message: str


@dataclass(frozen=True)
class ShutdownRequested:
    now: float


@dataclass(frozen=True)
class ActivateSteeringCurve:
    definition: SteeringCurveDefinition
    saved_profile_id: str | None = None
    saved_profile_revision: int | None = None
    requested_at: float = field(kw_only=True)


@dataclass(frozen=True)
class ServotronicStatusObserved:
    status: ServotronicStatus


@dataclass(frozen=True)
class ExecuteOperatorIntent:
    """A transport-independent operator intent submitted through a non-button adapter."""

    intent: OperatorIntent
    context: OperatorIntentContext = DEFAULT_OPERATOR_INTENT_CONTEXT

    def __post_init__(self) -> None:
        if not is_operator_intent(self.intent):
            raise TypeError(f"unsupported operator intent: {type(self.intent).__name__}")
        if not isinstance(self.context, OperatorIntentContext):
            raise TypeError("context must be an OperatorIntentContext")


ControllerInput = (
    KernelStarted
    | ReceivedCanFrame
    | TimerElapsed
    | ButtonFeedbackDeadlineReached
    | HighBeamStrobeDeadlineReached
    | CanReaderFailed
    | CanEffectExecutionFailed
    | SteeringActuatorFailed
    | InboxOverflowed
    | DeviceAdapterFailed
    | ShutdownRequested
    | ActivateSteeringCurve
    | ServotronicStatusObserved
    | ExecuteOperatorIntent
)
