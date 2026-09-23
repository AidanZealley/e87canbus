"""Single-owner simulation engine for the browser workbench."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from e87canbus.adapters.can_io import CanReceiver
from e87canbus.config import AppConfig, CanNetwork, simulator_config
from e87canbus.domain.buttons.profiles import ActiveButtonProfile
from e87canbus.domain.controller import ApplicationSnapshot
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
from e87canbus.runners.simulation.bus import InMemoryCanTopology, SimulatedCanTraceEntry
from e87canbus.runners.simulation.commands import (
    ResetSimulation,
    RunControlTimer,
    SetVehicleSignal,
    SetVehicleSweep,
    SilenceVehicleSignal,
)
from e87canbus.runners.simulation.session import build_session
from e87canbus.service import (
    ControllerAdapterSnapshot,
    ControllerWorkUnavailable,
    RuntimeExecution,
    RuntimeInputSink,
)

LOGGER = logging.getLogger(__name__)


def trace_entry_to_event(entry: SimulatedCanTraceEntry, session_id: int) -> dict[str, Any]:
    return {
        "type": "frame",
        "session_id": session_id,
        "sequence": entry.sequence,
        "network": entry.network.value,
        "source": entry.source,
        "arbitration_id": entry.frame.arbitration_id,
        "arbitration_id_hex": f"0x{entry.frame.arbitration_id:x}",
        "data_hex": entry.frame.data.hex(),
        "is_extended_id": entry.frame.is_extended_id,
        "monotonic_s": entry.monotonic_s,
    }


class SimulatedControllerRuntime:
    """Selected simulated adapters and devices; owned by ``ControllerLoop``."""

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
        self._previous_projection: ControllerAdapterSnapshot | None = None
        self._previous_diagnostics: DiagnosticSnapshot | None = None
        self._frame_history = {network: [0, 0, 0, 0] for network in CanNetwork}
        self.topology: InMemoryCanTopology
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

    def start(self, submit_input: RuntimeInputSink | None = None) -> RuntimeExecution:
        del submit_input
        if self._started:
            raise RuntimeError("simulated controller runtime may be started exactly once")
        self._started = True
        self._execution_commits = []
        self._build_session()
        return self._complete(())

    def execute(self, command: object) -> RuntimeExecution:
        self._require_started()
        if self.kernel.health.fatal and not isinstance(command, ResetSimulation):
            raise ControllerWorkUnavailable(
                "simulation session has fatal kernel health; reset required"
            )

        self._execution_commits = []
        before_sequence = self.topology.latest_sequence
        match command:
            case RunControlTimer(now):
                self.vehicle.emit()
                self._drain_kernel_inputs()
                self._dispatch(TimerElapsed(now))
            case SetVehicleSignal() | SilenceVehicleSignal() | SetVehicleSweep():
                self.vehicle.execute(command)
            case ReceivedCanFrame():
                self._dispatch(command)
            case ResetSimulation():
                replaced_session_id = self._session_id
                self._dispatch(ShutdownRequested(self._clock()))
                if self.kernel.health.fatal:
                    LOGGER.error(
                        "reset replaced simulation session %d with fatal diagnostics; "
                        "the new session starts healthy",
                        replaced_session_id,
                    )
                self._build_session()
                before_sequence = 0
                return self._complete(())
            case ActivateButtonProfile() | ActivateSteeringCurve() | ExecuteOperatorIntent():
                self._dispatch(command)
            case InboxOverflowed():
                self._dispatch(command)
                if self.kernel.health.fatal:
                    self._dispatch(ShutdownRequested(self._clock()))
            case _:
                raise TypeError(f"unsupported simulation command: {command!r}")

        return self._process_pending(before_sequence)

    def timer(self, now: float) -> RuntimeExecution | None:
        if self.kernel.health.fatal:
            return None
        return self.execute(RunControlTimer(now))

    def shutdown(self, now: float | None = None) -> RuntimeExecution:
        del now
        self._require_started()
        self._execution_commits = []
        before_sequence = self.topology.latest_sequence
        self._dispatch(ShutdownRequested(self._clock()))
        return self._process_pending(before_sequence)

    def close(self) -> None:
        """The in-process simulation runtime has no external endpoints to close."""

    def _build_session(self) -> None:
        self._session_id += 1
        session = build_session(
            self.config,
            self._clock,
            button_profile=self._button_profile,
            button_profile_saved_revision=self._initial_button_profile_revision,
            initial_steering_curve=self._initial_steering_curve,
        )
        self.topology = session.topology
        self.pi_buses = session.pi_buses
        self.vehicle = session.vehicle
        self.kernel = session.kernel

        startup = self._dispatch(KernelStarted(self._clock()))
        if startup is None:
            raise RuntimeError("simulation kernel did not start")
        self.vehicle.drain_pending()
        self.topology.clear_trace()

    def _process_pending(
        self,
        before_sequence: int,
    ) -> RuntimeExecution:
        self._drain_kernel_inputs()
        self.vehicle.drain_pending()

        return self._complete(
            tuple(
                trace_entry_to_event(entry, self._session_id)
                for entry in self.topology.trace()
                if entry.sequence > before_sequence
            ),
        )

    def projection(
        self,
    ) -> tuple[ApplicationSnapshot, DiagnosticSnapshot, ControllerAdapterSnapshot]:
        diagnostics = self.kernel.diagnostics()
        health = diagnostics.health
        diagnostics = replace(
            diagnostics,
            health=replace(
                health,
                networks=tuple(
                    replace(
                        network,
                        received_frames=network.received_frames
                        + self._frame_history[network.network][0],
                        decoded_frames=network.decoded_frames
                        + self._frame_history[network.network][1],
                        ignored_frames=network.ignored_frames
                        + self._frame_history[network.network][2],
                        malformed_frames=network.malformed_frames
                        + self._frame_history[network.network][3],
                    )
                    for network in health.networks
                ),
            ),
        )
        return self.kernel.snapshot(), diagnostics, self._adapter_projection()

    @property
    def terminal(self) -> bool:
        # A fatal simulated session stays available for the explicit reset command.
        return False

    def _complete(
        self,
        events: tuple[dict[str, Any], ...],
    ) -> RuntimeExecution:
        changed_topics = {
            topic for commit in self._execution_commits for topic in commit.changed_topics
        }
        projection = self._adapter_projection()
        diagnostics = self.kernel.diagnostics()
        previous = self._previous_projection
        previous_diagnostics = self._previous_diagnostics
        if (
            previous is not None
            and previous.simulation_session_id != projection.simulation_session_id
            and previous_diagnostics is not None
        ):
            for network in previous_diagnostics.health.networks:
                history = self._frame_history[network.network]
                history[0] += network.received_frames
                history[1] += network.decoded_frames
                history[2] += network.ignored_frames
                history[3] += network.malformed_frames
        self._previous_projection = projection
        self._previous_diagnostics = diagnostics
        commit_count = len(self._execution_commits)
        return RuntimeExecution(events, frozenset(changed_topics), commit_count)

    def _drain_kernel_inputs(self) -> int:
        processed = 0
        ordered_networks = tuple(network for network in CanNetwork if network in self.pi_buses)
        while True:
            found_frame = False
            for network in ordered_networks:
                frame = self.pi_buses[network].receive(timeout_s=0)
                if frame is None:
                    continue
                found_frame = True
                processed += 1
                observed_at = self._clock()
                self._dispatch(ReceivedCanFrame(network, frame, observed_at))
            if not found_frame:
                return processed

    def _dispatch(self, kernel_input: ControllerInput) -> Commit | None:
        commit = self.kernel.dispatch(kernel_input)
        if commit is not None:
            self._execution_commits.append(commit)
        return commit

    def _adapter_projection(self) -> ControllerAdapterSnapshot:
        return ControllerAdapterSnapshot(simulation_session_id=self._session_id)

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("simulated controller runtime has not started")
