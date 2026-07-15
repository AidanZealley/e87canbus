"""Validated physical/simulated adapter selection for the unified controller."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.application.controller import ApplicationSnapshot
from e87canbus.config import AppConfig, CanNetwork, default_config, simulator_config
from e87canbus.features.steering import CurveInterpolation
from e87canbus.live import LiveControllerRuntime
from e87canbus.runtime import (
    SUPPORTED_STEERING_CURVE_INTERPOLATIONS,
    ActivateSteeringCurve,
    DiagnosticSnapshot,
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
    ObservedDeviceSnapshot,
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
    SetDeviceStatus,
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
    StepButton,
)


class CanAdapterKind(StrEnum):
    SOCKETCAN = "socketcan"
    VIRTUAL = "virtual"
    DISABLED = "disabled"


class DeviceRole(StrEnum):
    BUTTON_PAD = "button_pad"


class DeviceSource(StrEnum):
    PHYSICAL = "physical"
    EMULATED = "emulated"
    OBSERVER = "observer"
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
class DeviceAdapterSelection:
    role: DeviceRole
    source: DeviceSource


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
            authorities = [
                item
                for item in self.device_adapters
                if item.role is role
                and item.source in (DeviceSource.PHYSICAL, DeviceSource.EMULATED)
            ]
            if len(authorities) > 1:
                raise ValueError(f"duplicate ingress authority for device role {role.value}")

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
        runtime: ControllerRuntimeAdapter = _SimulatedRuntimeAdapter(
            SimulatedControllerRuntime(
                config=selected_config,
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
    StepButton,
    RunControlTimer,
    SetVehicleSpeed,
    SilenceVehicleSpeed,
    SetEngineRpm,
    SilenceEngineRpm,
    SetOilTemperature,
    SilenceOilTemperature,
    SetCoolantTemperature,
    SilenceCoolantTemperature,
    SetDeviceStatus,
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
                execution.compatibility_snapshot,
                execution.events,
                execution.changed_topics,
                execution.commit_count,
            )
        raise TypeError(f"unsupported simulated controller work: {work!r}")

    def timer(self, now: float) -> RuntimeExecution | None:
        try:
            return self._execution(self._runtime.execute(RunControlTimer(now)))
        except SimulationSessionFailed:
            return None

    def shutdown(self, now: float) -> RuntimeExecution | None:
        del now
        return self._execution(self._runtime.shutdown())

    def projection(
        self,
    ) -> tuple[ApplicationSnapshot, DiagnosticSnapshot, ControllerAdapterSnapshot]:
        snapshot = self._runtime.snapshot()
        return (
            snapshot.application,
            self._runtime.kernel.diagnostics(),
            ControllerAdapterSnapshot(
                simulation_session_id=snapshot.session_id,
                led_colours=snapshot.led_colours,
                next_pressed=snapshot.next_pressed,
                devices=tuple(
                    ObservedDeviceSnapshot(
                        id=device.id.value,
                        label=device.label,
                        status=device.status.value,
                        reason=None if device.reason is None else device.reason.value,
                    )
                    for device in snapshot.devices
                ),
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
        if previous is None:
            changed_topics.add(StateTopic.DEVICES)
        else:
            if (
                previous.devices != result.snapshot.devices
                or previous.networks != result.snapshot.networks
                or previous.steering_controller != result.snapshot.steering_controller
            ):
                changed_topics.add(StateTopic.DEVICES)
            if (
                previous.led_colours != result.snapshot.led_colours
                or previous.next_pressed != result.snapshot.next_pressed
            ):
                changed_topics.add(StateTopic.BUTTONS)
        self._previous_snapshot = result.snapshot
        commit_count = len(result.commits)
        if commit_count == 0 and changed_topics:
            commit_count = 1
        return RuntimeExecution(
            result,
            result.snapshot,
            result.events,
            frozenset(changed_topics),
            commit_count,
        )
