"""Single-owner vehicle simulation for the browser workbench."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from e87canbus.adapters.can_io import CanReceiver
from e87canbus.config import AppConfig, CanNetwork, simulator_config
from e87canbus.domain.buttons.profiles import ActiveButtonProfile
from e87canbus.domain.controller import ApplicationSnapshot
from e87canbus.domain.events import ButtonPressed
from e87canbus.domain.steering.curves import ActiveSteeringCurve
from e87canbus.kernel import (
    ActivateButtonProfile,
    ActivateSteeringCurve,
    Commit,
    ControllerInput,
    CoordinatorKernel,
    DiagnosticSnapshot,
    ExecuteOperatorIntent,
    InboxOverflowed,
    KernelStarted,
    ReceivedCanFrame,
    ShutdownRequested,
    TimerElapsed,
)
from e87canbus.runners.simulation.commands import (
    ResetSimulation,
    SetVehicleSignal,
    SetVehicleSweep,
    SilenceVehicleSignal,
)
from e87canbus.runners.simulation.session import build_session
from e87canbus.service import (
    ControllerWorkUnavailable,
    RuntimeExecution,
    RuntimeInputSink,
)

LOGGER = logging.getLogger(__name__)


class SimulatedControllerRuntime:
    """Run synthetic vehicle frames through the production kernel input path."""

    def __init__(
        self,
        *,
        config: AppConfig | None = None,
        clock: Callable[[], float] = time.monotonic,
        button_profile: ActiveButtonProfile | None = None,
    ) -> None:
        self.config = config or simulator_config()
        self._clock = clock
        self._button_profile = button_profile
        self._session_id = 0
        self._started = False
        self._initial_steering_curve: ActiveSteeringCurve | None = None
        self._initial_button_profile_revision: int | None = None
        self._execution_commits: list[Commit] = []
        self.pi_buses: dict[CanNetwork, CanReceiver]
        self.kernel: CoordinatorKernel

    def configure_initial_steering_curve(self, curve: ActiveSteeringCurve) -> None:
        if self._started:
            raise RuntimeError("initial steering curve must be configured before startup")
        self._initial_steering_curve = curve

    def configure_initial_button_profile(
        self,
        profile: ActiveButtonProfile,
        saved_profile_revision: int | None = None,
    ) -> None:
        if self._started:
            raise RuntimeError("initial button profile must be configured before startup")
        self._button_profile = profile
        self._initial_button_profile_revision = saved_profile_revision

    def start(self, submit_input: RuntimeInputSink) -> RuntimeExecution:
        del submit_input
        if self._started:
            raise RuntimeError("simulated controller runtime may be started exactly once")
        self._started = True
        self._build_session()
        return self._complete()

    def execute(self, command: object) -> RuntimeExecution:
        self._require_started()
        if self.kernel.health.fatal and not isinstance(command, ResetSimulation):
            raise ControllerWorkUnavailable(
                "simulation session has fatal kernel health; reset required"
            )

        self._execution_commits = []
        match command:
            case SetVehicleSignal() | SilenceVehicleSignal() | SetVehicleSweep():
                self.vehicle.execute(command)
                self._drain_vehicle_frames()
            case (
                ReceivedCanFrame()
                | ActivateButtonProfile()
                | ActivateSteeringCurve()
                | ExecuteOperatorIntent()
                | ButtonPressed()
            ):
                self._dispatch(command)
            case ResetSimulation():
                if self.kernel.health.fatal:
                    LOGGER.error(
                        "reset replaced simulation session %d with fatal diagnostics",
                        self._session_id,
                    )
                self._dispatch(ShutdownRequested())
                self._build_session()
            case InboxOverflowed():
                self._dispatch(command)
                if self.kernel.health.fatal:
                    self._dispatch(ShutdownRequested())
            case _:
                raise TypeError(f"unsupported simulation command: {command!r}")
        return self._complete()

    def timer(self, now: float) -> RuntimeExecution | None:
        if self.kernel.health.fatal:
            return None
        self._execution_commits = []
        self.vehicle.emit()
        self._drain_vehicle_frames()
        self._dispatch(TimerElapsed(now))
        return self._complete()

    def shutdown(self) -> RuntimeExecution | None:
        self._require_started()
        self._execution_commits = []
        self._dispatch(ShutdownRequested())
        return self._complete()

    def close(self) -> None:
        """The in-process simulation has no external endpoints to close."""

    def projection(
        self,
    ) -> tuple[ApplicationSnapshot, DiagnosticSnapshot, int | None]:
        return self.kernel.snapshot(), self.kernel.diagnostics(), self._session_id

    @property
    def terminal(self) -> bool:
        # A fatal simulated session remains available for explicit reset.
        return False

    def _build_session(self) -> None:
        self._session_id += 1
        session = build_session(
            self.config,
            self._clock,
            button_profile=self._button_profile,
            button_profile_saved_revision=self._initial_button_profile_revision,
            initial_steering_curve=self._initial_steering_curve,
        )
        self.pi_buses = session.pi_buses
        self.vehicle = session.vehicle
        self.kernel = session.kernel
        if self._dispatch(KernelStarted()) is None:
            raise RuntimeError("simulation kernel did not start")

    def _drain_vehicle_frames(self) -> None:
        for network in CanNetwork:
            bus = self.pi_buses.get(network)
            if bus is None:
                continue
            while (frame := bus.receive(timeout_s=0)) is not None:
                self._dispatch(ReceivedCanFrame(network, frame, self._clock()))

    def _dispatch(self, kernel_input: ControllerInput) -> Commit | None:
        commit = self.kernel.dispatch(kernel_input)
        if commit is not None:
            self._execution_commits.append(commit)
        return commit

    def _complete(self) -> RuntimeExecution:
        return RuntimeExecution(
            changed_topics=frozenset(
                topic for commit in self._execution_commits for topic in commit.changed_topics
            ),
            commit_count=len(self._execution_commits),
        )

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("simulated controller runtime has not started")
