"""The single-owner coordinator kernel: inputs, the state machine, and its commit contract.

Import the public surface from this package (``from e87canbus.kernel import ...``);
the submodules split the former ``runtime.py`` into inputs, health, the commit
contract and the kernel itself, but external callers should not depend on that layout.
"""

from e87canbus.kernel.commit import (
    INITIAL_KERNEL_TOPICS,
    Commit,
    DiagnosticSnapshot,
    KernelLifecycle,
    StateTopic,
    changed_controller_topics,
)
from e87canbus.kernel.health import (
    DeviceRuntimeHealth,
    NetworkRuntimeHealth,
    RuntimeFault,
    RuntimeFaultKind,
    RuntimeHealth,
)
from e87canbus.kernel.inputs import (
    ActivateSteeringCurve,
    CanEffectExecutionFailed,
    CanReaderFailed,
    ControllerInput,
    DeviceAdapterFailed,
    ExecuteOperatorIntent,
    InboxOverflowed,
    KernelStarted,
    ReceivedCanFrame,
    ServotronicStatusObserved,
    ShutdownRequested,
    SteeringActuatorFailed,
    TimerElapsed,
)
from e87canbus.kernel.kernel import CoordinatorKernel

__all__ = [
    "INITIAL_KERNEL_TOPICS",
    "ActivateSteeringCurve",
    "CanEffectExecutionFailed",
    "CanReaderFailed",
    "Commit",
    "ControllerInput",
    "CoordinatorKernel",
    "DeviceAdapterFailed",
    "DeviceRuntimeHealth",
    "DiagnosticSnapshot",
    "ExecuteOperatorIntent",
    "InboxOverflowed",
    "KernelLifecycle",
    "KernelStarted",
    "NetworkRuntimeHealth",
    "ReceivedCanFrame",
    "RuntimeFault",
    "RuntimeFaultKind",
    "RuntimeHealth",
    "ServotronicStatusObserved",
    "ShutdownRequested",
    "SteeringActuatorFailed",
    "StateTopic",
    "TimerElapsed",
    "changed_controller_topics",
]
