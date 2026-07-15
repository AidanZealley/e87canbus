"""Validated physical/simulated adapter selection for the unified controller."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.application.controller import ApplicationSnapshot
from e87canbus.config import AppConfig, CanNetwork, default_config, simulator_config
from e87canbus.device import DeviceAdapterSelection, DeviceRole, DeviceSource
from e87canbus.features.steering import CurveInterpolation
from e87canbus.live import LiveControllerRuntime
from e87canbus.runtime import (
    SUPPORTED_STEERING_CURVE_INTERPOLATIONS,
    ActivateSteeringCurve,
    DeviceAdapterFailed,
    DiagnosticSnapshot,
    InboxOverflowed,
    SetMaximumAssistance,
    SetSteeringMode,
    StateTopic,
)
from e87canbus.service import (
    ControllerAdapterSnapshot,
    ControllerCommandResult,
    ControllerMode,
    ControllerRuntimeAdapter,
    ControllerService,
    ObservedNetworkSnapshot,
    ObservedSteeringSnapshot,
    RuntimeExecution,
    RuntimeInputSink,
)
from e87canbus.simulation.devices import SimulatedSteeringController
from e87canbus.simulation.runtime import (
    PressButton,
    ReleaseButton,
    ResetSimulation,
    RunControlTimer,
    SetCoolantTemperature,
    SetEngineRpm,
    SetOilTemperature,
    SetVehicleSpeed,
    SilenceCoolantTemperature,
    SilenceEngineRpm,
    SilenceOilTemperature,
    SilenceVehicleSpeed,
    SimulatedControllerRuntime,
    SimulationCommand,
    SimulationSessionFailed,
    SimulatorSnapshot,
)


class CanAdapterKind(StrEnum):
    SOCKETCAN = "socketcan"
    VIRTUAL = "virtual"
    DISABLED = "disabled"


class SteeringCapability(StrEnum):
    SIMULATED = "simulated"
    PHYSICAL_EVIDENCE_GATED = "physical-evidence-gated"
    ABSENT = "absent"


@dataclass(frozen=True)
class CanAdapterSelection:
    network: CanNetwork
    kind: CanAdapterKind


@dataclass(frozen=True)
class CompositionSelection:
    mode: ControllerMode
    can_adapters: tuple[CanAdapterSelection, ...]
    device_adapters: tuple[DeviceAdapterSelection, ...]
    steering: SteeringCapability
    tx_grants: frozenset[CanNetwork] = frozenset()

    def __post_init__(self) -> None:
        networks = [item.network for item in self.can_adapters]
        if len(networks) != len(set(networks)):
            raise ValueError("each CAN network must have exactly one selected adapter")

        for role in DeviceRole:
            selected = [item for item in self.device_adapters if item.role is role]
            if len(selected) != 1:
                raise ValueError(
                    f"device role {role.value} must have exactly one selected source; "
                    "duplicate ingress authority is not allowed"
                )

        if self.steering is SteeringCapability.PHYSICAL_EVIDENCE_GATED:
            raise ValueError("physical steering has no evidence-backed implementation or grant")
        if self.mode is ControllerMode.LIVE:
            if any(item.kind is CanAdapterKind.VIRTUAL for item in self.can_adapters):
                raise ValueError("live composition cannot select simulation-only CAN decoding")
            if any(
                item.source is DeviceSource.EMULATED for item in self.device_adapters
            ):
                raise ValueError("live composition cannot select an emulated ingress authority")
            if self.steering is not SteeringCapability.ABSENT:
                raise ValueError("live composition has no physical steering capability")
        else:
            if any(item.kind is CanAdapterKind.SOCKETCAN for item in self.can_adapters):
                raise ValueError("simulated composition cannot select SocketCAN")
            if self.steering is not SteeringCapability.SIMULATED:
                raise ValueError("simulated composition requires the simulated steering adapter")

        by_network = {item.network: item.kind for item in self.can_adapters}
        button_source = self.device_source(DeviceRole.BUTTON_PAD)
        if button_source is DeviceSource.PHYSICAL and (
            self.mode is not ControllerMode.LIVE
            or by_network.get(CanNetwork.KCAN) is not CanAdapterKind.SOCKETCAN
        ):
            raise ValueError("physical button pad requires live SocketCAN K-CAN")
        if button_source is DeviceSource.EMULATED and (
            self.mode is not ControllerMode.SIMULATED
            or by_network.get(CanNetwork.KCAN) is not CanAdapterKind.VIRTUAL
        ):
            raise ValueError("emulated button pad requires simulated virtual K-CAN")
        if (
            button_source is DeviceSource.EMULATED
            and CanNetwork.KCAN not in self.tx_grants
        ):
            raise ValueError(
                "emulated button pad requires authorized simulated K-CAN output"
            )

    def device_source(self, role: DeviceRole) -> DeviceSource:
        return next(item.source for item in self.device_adapters if item.role is role)


def live_selection(config: AppConfig | None = None) -> CompositionSelection:
    selected = config or default_config()
    kcan_enabled = any(
        item.network is CanNetwork.KCAN and item.enabled for item in selected.can_networks
    )
    return CompositionSelection(
        mode=ControllerMode.LIVE,
        can_adapters=tuple(
            CanAdapterSelection(
                item.network,
                CanAdapterKind.SOCKETCAN if item.enabled else CanAdapterKind.DISABLED,
            )
            for item in selected.can_networks
        ),
        device_adapters=(
            DeviceAdapterSelection(
                DeviceRole.BUTTON_PAD,
                DeviceSource.PHYSICAL if kcan_enabled else DeviceSource.DISABLED,
            ),
        ),
        steering=SteeringCapability.ABSENT,
    )


def simulated_selection(config: AppConfig | None = None) -> CompositionSelection:
    selected = config or simulator_config()
    kcan_enabled = any(
        item.network is CanNetwork.KCAN and item.enabled for item in selected.can_networks
    )
    return CompositionSelection(
        mode=ControllerMode.SIMULATED,
        can_adapters=tuple(
            CanAdapterSelection(
                item.network,
                CanAdapterKind.VIRTUAL if item.enabled else CanAdapterKind.DISABLED,
            )
            for item in selected.can_networks
        ),
        device_adapters=(
            DeviceAdapterSelection(
                DeviceRole.BUTTON_PAD,
                DeviceSource.EMULATED if kcan_enabled else DeviceSource.DISABLED,
            ),
        ),
        steering=SteeringCapability.SIMULATED,
        tx_grants=frozenset(
            item.network for item in selected.can_networks if item.enabled and item.tx_enabled
        ),
    )


SteeringControllerFactory = Callable[
    [float, Callable[[], float]],
    SimulatedSteeringController,
]
SocketCanFactory = Callable[[str], SocketCanBus]


def build_controller_service(
    mode: ControllerMode,
    *,
    config: AppConfig | None = None,
    selection: CompositionSelection | None = None,
    clock: Callable[[], float] = time.monotonic,
    socketcan_factory: SocketCanFactory = SocketCanBus,
    steering_controller_factory: SteeringControllerFactory = SimulatedSteeringController,
    supported_steering_curve_interpolations: tuple[CurveInterpolation, ...] = (
        SUPPORTED_STEERING_CURVE_INTERPOLATIONS
    ),
) -> ControllerService:
    selected_config = config or (
        simulator_config() if mode is ControllerMode.SIMULATED else default_config()
    )
    selected = selection or (
        simulated_selection(selected_config)
        if mode is ControllerMode.SIMULATED
        else live_selection(selected_config)
    )
    if selected.mode is not mode:
        raise ValueError("composition selection mode does not match requested mode")
    _validate_network_selection(selected_config, selected)

    if mode is ControllerMode.SIMULATED:
        button_source = selected.device_source(DeviceRole.BUTTON_PAD)
        runtime: ControllerRuntimeAdapter = _SimulatedRuntimeAdapter(
            SimulatedControllerRuntime(
                config=selected_config,
                button_pad_source=button_source,
                clock=clock,
                steering_controller_factory=steering_controller_factory,
                supported_steering_curve_interpolations=(
                    supported_steering_curve_interpolations
                ),
            )
        )
    else:
        runtime = LiveControllerRuntime(
            selected_config,
            button_pad_source=selected.device_source(DeviceRole.BUTTON_PAD),
            tx_grants=selected.tx_grants,
            bus_factory=socketcan_factory,
            clock=clock,
        )
    return ControllerService(runtime, mode=mode, clock=clock)


def _validate_network_selection(
    config: AppConfig,
    selection: CompositionSelection,
) -> None:
    configured_networks = [item.network for item in config.can_networks]
    if len(configured_networks) != len(set(configured_networks)):
        raise ValueError("each CAN network may be configured at most once")
    by_network = {item.network: item for item in selection.can_adapters}
    if set(by_network) != set(configured_networks):
        raise ValueError("CAN adapter selections must match configured networks exactly")
    for configured in config.can_networks:
        selected = by_network.get(configured.network)
        expected_disabled = not configured.enabled
        if selected is None:
            raise ValueError(f"missing CAN adapter selection for {configured.network.value}")
        if expected_disabled != (selected.kind is CanAdapterKind.DISABLED):
            raise ValueError(
                f"CAN adapter selection disagrees with enabled state for "
                f"{configured.network.value}"
            )
        if configured.tx_enabled and configured.network not in selection.tx_grants:
            raise ValueError(
                f"CAN TX for {configured.network.value} requires an explicit network grant"
            )
        if configured.network in selection.tx_grants and not configured.tx_enabled:
            raise ValueError(
                f"CAN TX grant for {configured.network.value} has no enabled transmitter"
            )


_SIMULATION_COMMAND_TYPES = (
    PressButton,
    ReleaseButton,
    RunControlTimer,
    SetVehicleSpeed,
    SilenceVehicleSpeed,
    SetEngineRpm,
    SilenceEngineRpm,
    SetOilTemperature,
    SilenceOilTemperature,
    SetCoolantTemperature,
    SilenceCoolantTemperature,
    ResetSimulation,
)

_SEMANTIC_CONTROLLER_COMMAND_TYPES = (
    ActivateSteeringCurve,
    SetMaximumAssistance,
    SetSteeringMode,
)


class _SimulatedRuntimeAdapter:
    def __init__(self, runtime: SimulatedControllerRuntime) -> None:
        self._runtime = runtime
        self._previous_snapshot: SimulatorSnapshot | None = None
        self._previous_diagnostics: DiagnosticSnapshot | None = None
        self._frame_history = {
            network: [0, 0, 0, 0]
            for network in CanNetwork
        }

    @property
    def config(self) -> AppConfig:
        return self._runtime.config

    def start(self, submit_input: RuntimeInputSink) -> RuntimeExecution:
        del submit_input
        return self._execution(self._runtime.start())

    def execute(self, work: object) -> RuntimeExecution:
        if isinstance(work, _SIMULATION_COMMAND_TYPES):
            command: SimulationCommand = work
            return self._execution(self._runtime.execute(command))
        if isinstance(work, _SEMANTIC_CONTROLLER_COMMAND_TYPES):
            result = self._runtime.execute_controller_command(work)
            execution = self._execution(result)
            return RuntimeExecution(
                ControllerCommandResult(
                    result.snapshot.revision,
                    result.snapshot.fatal,
                ),
                execution.events,
                execution.changed_topics,
                execution.commit_count,
            )
        if isinstance(work, (InboxOverflowed, DeviceAdapterFailed)):
            return self._execution(self._runtime.execute_controller_failure(work))
        raise TypeError(f"unsupported simulated controller work: {work!r}")

    def timer(self, now: float) -> RuntimeExecution | None:
        try:
            return self._execution(self._runtime.execute(RunControlTimer(now)))
        except SimulationSessionFailed:
            return None

    def shutdown(self, now: float) -> RuntimeExecution | None:
        del now
        return self._execution(self._runtime.shutdown())

    def close(self) -> None:
        """The in-process simulation runtime has no external endpoints to close."""

    def projection(
        self,
    ) -> tuple[ApplicationSnapshot, DiagnosticSnapshot, ControllerAdapterSnapshot]:
        snapshot = self._runtime.snapshot()
        diagnostics = self._runtime.kernel.diagnostics()
        health = diagnostics.health
        diagnostics = replace(
            diagnostics,
            health=replace(
                health,
                networks=tuple(
                    replace(
                        network,
                        received_frames=(
                            network.received_frames + self._frame_history[network.network][0]
                        ),
                        decoded_frames=(
                            network.decoded_frames + self._frame_history[network.network][1]
                        ),
                        ignored_frames=(
                            network.ignored_frames + self._frame_history[network.network][2]
                        ),
                        malformed_frames=(
                            network.malformed_frames + self._frame_history[network.network][3]
                        ),
                    )
                    for network in health.networks
                ),
            ),
        )
        return (
            snapshot.application,
            diagnostics,
            ControllerAdapterSnapshot(
                simulation_session_id=snapshot.session_id,
                led_colours=snapshot.led_colours,
                devices=snapshot.devices,
                networks=tuple(
                    ObservedNetworkSnapshot(
                        network=network.config.network,
                        label=network.config.label,
                        interface=network.config.interface,
                        bitrate=network.config.bitrate,
                        connected=network.connected,
                        nodes=network.nodes,
                    )
                    for network in snapshot.networks
                ),
                steering=ObservedSteeringSnapshot(
                    effective_assistance=snapshot.steering_controller.effective_assistance,
                    last_command_reason=(
                        None
                        if snapshot.steering_controller.last_command_reason is None
                        else snapshot.steering_controller.last_command_reason.value
                    ),
                    watchdog_timed_out=snapshot.steering_controller.watchdog_timed_out,
                ),
                effects=self._runtime.effect_diagnostics,
            ),
        )

    @property
    def terminal(self) -> bool:
        # A fatal simulated session stays available for the explicit reset command.
        return False

    def _execution(self, result: object) -> RuntimeExecution:
        from e87canbus.simulation.runtime import SimulationResult

        if not isinstance(result, SimulationResult):
            raise TypeError(f"unexpected simulated runtime result: {result!r}")
        changed_topics: set[StateTopic] = set()
        for commit in result.commits:
            changed_topics.update(commit.changed_topics)
        previous = self._previous_snapshot
        diagnostics = self._runtime.kernel.diagnostics()
        previous_diagnostics = self._previous_diagnostics
        if (
            previous is not None
            and previous.session_id != result.snapshot.session_id
            and previous_diagnostics is not None
        ):
            for network in previous_diagnostics.health.networks:
                history = self._frame_history[network.network]
                history[0] += network.received_frames
                history[1] += network.decoded_frames
                history[2] += network.ignored_frames
                history[3] += network.malformed_frames
        if previous is None:
            changed_topics.add(StateTopic.DEVICES)
        else:
            if (
                previous.devices != result.snapshot.devices
                or previous.networks != result.snapshot.networks
                or previous.steering_controller != result.snapshot.steering_controller
            ):
                changed_topics.add(StateTopic.DEVICES)
            if previous.led_colours != result.snapshot.led_colours:
                changed_topics.add(StateTopic.BUTTONS)
        self._previous_snapshot = result.snapshot
        self._previous_diagnostics = diagnostics
        if previous_diagnostics is not None and diagnostics.health != previous_diagnostics.health:
            changed_topics.add(StateTopic.HEALTH)
            if any(
                current.fault != prior.fault
                for current, prior in zip(
                    diagnostics.health.devices,
                    previous_diagnostics.health.devices,
                    strict=True,
                )
            ):
                changed_topics.add(StateTopic.DEVICES)
        commit_count = len(result.commits)
        if commit_count == 0 and changed_topics:
            commit_count = 1
        return RuntimeExecution(
            result,
            result.events,
            frozenset(changed_topics),
            commit_count,
        )
