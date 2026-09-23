"""The bounded single-owner controller service: lifecycle plus its projection DTOs.

Import from this package (``from e87canbus.service import ...``); the split
between the service lifecycle and its diagnostics DTOs is an internal layout.
"""

from e87canbus.service.diagnostics import (
    ControllerAdapterSnapshot,
    ControllerLoopSnapshot,
    InboxDiagnostics,
    PersistenceDiagnostics,
    PublisherDiagnostics,
    RuntimeExecution,
    ServiceDiagnostics,
)
from e87canbus.service.loop import (
    ControllerInboxFull,
    ControllerLoop,
    ControllerLoopError,
    ControllerLoopLifecycle,
    ControllerLoopNotRunning,
    ControllerRuntime,
    ControllerWorkUnavailable,
    RuntimeInputSink,
    RuntimeNotification,
)

__all__ = [
    "ControllerAdapterSnapshot",
    "ControllerInboxFull",
    "ControllerRuntime",
    "ControllerLoop",
    "ControllerLoopError",
    "ControllerLoopLifecycle",
    "ControllerLoopNotRunning",
    "ControllerLoopSnapshot",
    "ControllerWorkUnavailable",
    "InboxDiagnostics",
    "PersistenceDiagnostics",
    "PublisherDiagnostics",
    "RuntimeExecution",
    "RuntimeInputSink",
    "RuntimeNotification",
    "ServiceDiagnostics",
]
