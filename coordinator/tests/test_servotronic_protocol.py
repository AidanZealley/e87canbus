from __future__ import annotations

from dataclasses import replace

import pytest
from e87canbus.application.events import ConfigureServotronicCurve
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
    KernelStarted,
    ReceivedCanFrame,
    ServotronicStatusObserved,
    TimerElapsed,
)
from e87canbus.servotronic_protocol import (
    CurveResult,
    CurveSource,
    ServotronicStatus,
    pack_curve,
    pack_status,
    unpack_curve,
    unpack_status,
)


def test_fixed_curve_and_status_payloads_round_trip() -> None:
    active = initial_active_steering_curve()
    payload = pack_curve(active.definition, active.activation_revision)
    assert len(payload) == 44
    definition, revision, crc = unpack_curve(payload)
    assert definition == active.definition
    assert revision == active.activation_revision
    status = ServotronicStatus(
        CurveResult.ACCEPTED, CurveSource.COORDINATOR_RAM, revision, crc,
        425, 700, 90, True, 0,
    )
    assert unpack_status(pack_status(status)) == status
    with pytest.raises(ValueError, match="CRC"):
        unpack_curve(payload[:-1] + bytes((payload[-1] ^ 1,)))


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
            encode_hello(
                DeviceHelloPayload(1, 1, session, 0), ids.servotronic_controller_hello
            ),
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
    assert kernel.snapshot().curve_configuration_available is True
    registered = _register(kernel, 1, 0.1)
    assert len(_curve_effects(registered)) == 1
    assert (
        registered.snapshot.steering_curve_activation_status
        is SteeringCurveActivationStatus.ACTIVATING
    )

    accepted = kernel.dispatch(ServotronicStatusObserved(_matching_status(kernel)))
    assert accepted is not None
    assert (
        accepted.snapshot.steering_curve_activation_status
        is SteeringCurveActivationStatus.ACTIVE
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
        ServotronicStatusObserved(
            replace(_matching_status(kernel), result=CurveResult.BAD_CRC)
        )
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
    assert kernel.snapshot().curve_configuration_available is False
    with pytest.raises(FeatureUnavailable, match="output adapter is unavailable"):
        kernel.dispatch(
            ActivateSteeringCurve(
                kernel.snapshot().active_steering_curve.definition,
                requested_at=1.0,
            )
        )
