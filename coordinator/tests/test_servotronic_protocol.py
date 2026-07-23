from __future__ import annotations

import struct
import zlib
from dataclasses import replace

import pytest
from e87canbus.application.events import ConfigureServotronicCurve
from e87canbus.application.intents import SetMaximumAssistance
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.device import DeviceRole, DeviceSource
from e87canbus.device_registry import FeatureUnavailable
from e87canbus.features.steering import (
    SteeringCurveActivationStatus,
    initial_active_steering_curve,
)
from e87canbus.protocol.can import (
    DeviceHeartbeatPayload,
    DeviceHelloPayload,
    encode_heartbeat,
    encode_hello,
)
from e87canbus.runtime import (
    ActivateSteeringCurve,
    CoordinatorKernel,
    DeviceAdapterFailed,
    ExecuteOperatorIntent,
    KernelStarted,
    ReceivedCanFrame,
    ServotronicStatusObserved,
    TimerElapsed,
)
from e87canbus.service import observed_servotronic_snapshot
from e87canbus.servotronic_protocol import (
    ControlMode,
    CurveResult,
    CurveSource,
    ServotronicStatus,
    pack_control,
    pack_curve,
    unpack_status,
)


def test_control_payload_encodes_manual_override() -> None:
    assert pack_control(0.75, ControlMode.MANUAL) == bytes((1, 3, 0xEE, 0x02, 1))


def test_fixed_curve_and_status_payloads_round_trip() -> None:
    active = initial_active_steering_curve()
    payload = pack_curve(active.definition, active.activation_revision)
    assert len(payload) == 44
    unpacked = struct.unpack("<BBBBI8H8HI", payload)
    assert unpacked[:5] == (1, 1, 1, 1, active.activation_revision)
    assert unpacked[5:13] == tuple(point.speed_deci_kph for point in active.definition.points)
    assert unpacked[13:21] == tuple(
        point.assistance_per_mille for point in active.definition.points
    )
    crc = unpacked[21]
    assert crc == zlib.crc32(payload[:-4])
    status = ServotronicStatus(
        CurveResult.ACCEPTED,
        CurveSource.COORDINATOR_RAM,
        active.activation_revision,
        crc,
        425,
        700,
        90,
        True,
        0,
    )
    status_payload = struct.pack(
        "<BBBBIIHHBBB",
        1,
        2,
        status.result,
        status.source,
        status.activation_revision,
        status.curve_crc32,
        status.speed_deci_kph,
        status.assistance_per_mille,
        status.pwm_duty,
        int(status.speed_fresh),
        status.inhibit_reason,
    )
    assert unpack_status(status_payload) == status


def _physical_kernel(*, config_available: bool = True) -> CoordinatorKernel:
    active = initial_active_steering_curve()
    kernel = CoordinatorKernel(
        active_steering_curve=active,
        device_sources={DeviceRole.SERVOTRONIC_CONTROLLER: DeviceSource.PHYSICAL},
        servotronic_output_available=False,
        servotronic_config_available=config_available,
    )
    kernel.dispatch(KernelStarted(0))
    return kernel


def _register(kernel: CoordinatorKernel, session: int, at: float):
    ids = CustomCanIds()
    hello = kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            encode_hello(DeviceHelloPayload(1, 1, session, 0), ids.servotronic_controller_hello),
            at,
        )
    )
    heartbeat = kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            encode_heartbeat(
                DeviceHeartbeatPayload(1, session, kernel.controller_session_id, 0, 0),
                ids.servotronic_controller_heartbeat,
            ),
            at + 0.1,
        )
    )
    assert hello is not None and heartbeat is not None
    return heartbeat


def _curve_effects(commit) -> tuple[ConfigureServotronicCurve, ...]:
    return tuple(
        request.effect
        for request in commit.effects
        if isinstance(request.effect, ConfigureServotronicCurve)
    )


def _matching_status(kernel: CoordinatorKernel) -> ServotronicStatus:
    active = kernel.snapshot().active_steering_curve
    payload = pack_curve(active.definition, active.activation_revision)
    return ServotronicStatus(
        CurveResult.ACCEPTED,
        CurveSource.COORDINATOR_RAM,
        active.activation_revision,
        int.from_bytes(payload[-4:], "little"),
        0,
        1000,
        180,
        True,
        0,
    )


def test_physical_registration_reconciles_once_and_matching_status_activates() -> None:
    kernel = _physical_kernel()
    assert kernel.snapshot().curve_activation_available is True
    registered = _register(kernel, 1, 0.1)
    assert len(_curve_effects(registered)) == 1
    assert (
        registered.snapshot.steering_curve_activation_status
        is SteeringCurveActivationStatus.ACTIVATING
    )

    accepted = kernel.dispatch(ServotronicStatusObserved(_matching_status(kernel)))
    assert accepted is not None
    assert (
        accepted.snapshot.steering_curve_activation_status is SteeringCurveActivationStatus.ACTIVE
    )

    timer = kernel.dispatch(TimerElapsed(1.0))
    assert timer is not None and _curve_effects(timer) == ()
    ordinary_status = kernel.dispatch(ServotronicStatusObserved(_matching_status(kernel)))
    assert ordinary_status is not None and _curve_effects(ordinary_status) == ()


def test_rejection_or_mismatch_cannot_claim_active_or_replace_coordinator_curve() -> None:
    kernel = _physical_kernel()
    _register(kernel, 1, 0.1)
    active = kernel.snapshot().active_steering_curve
    rejected = kernel.dispatch(
        ServotronicStatusObserved(replace(_matching_status(kernel), result=CurveResult.BAD_CRC))
    )
    assert rejected is not None
    assert (
        rejected.snapshot.steering_curve_activation_status
        is SteeringCurveActivationStatus.ACTIVATION_FAILED
    )
    assert rejected.snapshot.active_steering_curve == active

    mismatched = kernel.dispatch(
        ServotronicStatusObserved(replace(_matching_status(kernel), curve_crc32=0))
    )
    assert mismatched is not None
    assert (
        mismatched.snapshot.steering_curve_activation_status
        is SteeringCurveActivationStatus.ACTIVATING
    )
    assert mismatched.snapshot.active_steering_curve == active


def test_expiration_and_new_session_cause_one_fresh_reconciliation() -> None:
    kernel = _physical_kernel()
    _register(kernel, 1, 0.1)
    kernel.dispatch(ServotronicStatusObserved(_matching_status(kernel)))
    expired = kernel.dispatch(TimerElapsed(3.3))
    assert expired is not None and _curve_effects(expired) == ()
    registered = _register(kernel, 2, 4.0)
    assert len(_curve_effects(registered)) == 1
    later = kernel.dispatch(TimerElapsed(4.5))
    assert later is not None and _curve_effects(later) == ()


def test_no_config_capability_never_emits_curve_and_refuses_activation() -> None:
    kernel = _physical_kernel(config_available=False)
    registered = _register(kernel, 1, 0.1)
    assert _curve_effects(registered) == ()
    assert kernel.snapshot().curve_activation_available is False
    with pytest.raises(FeatureUnavailable, match="output adapter is unavailable"):
        kernel.dispatch(
            ActivateSteeringCurve(
                kernel.snapshot().active_steering_curve.definition,
                requested_at=1.0,
            )
        )


def test_curve_activation_config_path_reports_controller_state_not_output() -> None:
    # config path is available but the controller has not registered; the requirement predicate
    # skips the output-adapter checks and reports the controller lifecycle instead.
    kernel = _physical_kernel(config_available=True)
    with pytest.raises(FeatureUnavailable, match="servotronic controller is"):
        kernel.dispatch(
            ActivateSteeringCurve(
                kernel.snapshot().active_steering_curve.definition,
                requested_at=1.0,
            )
        )


def test_maximum_assistance_requires_output_even_with_curve_config() -> None:
    kernel = _physical_kernel(config_available=True)
    _register(kernel, 1, 0.1)
    with pytest.raises(FeatureUnavailable, match="output adapter is unavailable"):
        kernel.dispatch(ExecuteOperatorIntent(SetMaximumAssistance(True)))


def test_observed_servotronic_snapshot_uses_canonical_wire_strings() -> None:
    status = ServotronicStatus(
        CurveResult.ACCEPTED,
        CurveSource.BUILTIN_FALLBACK,
        7,
        0xABCD,
        425,
        700,
        90,
        True,
        2,
        ControlMode.MANUAL,
    )
    observed = observed_servotronic_snapshot(status)
    assert observed.last_command_reason == "manual"
    assert observed.active_curve_source == "builtin_fallback"
    assert observed.inhibit_reason == "stale_speed"
    assert observed.effective_assistance == 0.7
    assert observed.observed_speed_kph == 42.5
    assert observed.active_curve_revision == 7
    assert observed.active_curve_crc32 == 0xABCD
    assert observed.pwm_duty == 90
    assert observed.speed_fresh is True
    assert observed.watchdog_timed_out is False


def test_observed_servotronic_snapshot_maps_modes_and_clamps_unknown_inhibit() -> None:
    base = ServotronicStatus(
        CurveResult.ACCEPTED,
        CurveSource.COORDINATOR_RAM,
        1,
        0,
        0,
        0,
        0,
        False,
        99,
        ControlMode.MAXIMUM,
    )
    observed = observed_servotronic_snapshot(base)
    assert observed.active_curve_source == "coordinator_ram"
    assert observed.last_command_reason == "maximum"
    assert observed.inhibit_reason == "can_fault"
    assert (
        observed_servotronic_snapshot(
            replace(base, control_mode=ControlMode.AUTO)
        ).last_command_reason
        == "auto"
    )


def test_kernel_drops_retained_status_when_controller_expires() -> None:
    kernel = _physical_kernel()
    _register(kernel, 1, 0.1)
    status = _matching_status(kernel)
    kernel.dispatch(ServotronicStatusObserved(status))
    assert kernel.servotronic_status == status
    kernel.dispatch(TimerElapsed(3.3))
    assert kernel.servotronic_status is None


def test_kernel_drops_retained_status_on_adapter_failure() -> None:
    kernel = _physical_kernel()
    _register(kernel, 1, 0.1)
    kernel.dispatch(ServotronicStatusObserved(_matching_status(kernel)))
    assert kernel.servotronic_status is not None
    kernel.dispatch(DeviceAdapterFailed(DeviceRole.SERVOTRONIC_CONTROLLER, 1.0, "adapter fault"))
    assert kernel.servotronic_status is None


def test_kernel_drops_retained_status_on_new_controller_session() -> None:
    kernel = _physical_kernel()
    _register(kernel, 1, 0.1)
    kernel.dispatch(ServotronicStatusObserved(_matching_status(kernel)))
    assert kernel.servotronic_status is not None
    _register(kernel, 2, 4.0)
    assert kernel.servotronic_status is None
