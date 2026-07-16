from __future__ import annotations

from typing import cast

from e87canbus.config import CanNetwork
from e87canbus.device import DeviceSource
from e87canbus.protocol.can import (
    DeviceHeartbeatPayload,
    DeviceHelloPayload,
    encode_heartbeat,
    encode_hello,
)
from e87canbus.runtime import ReceivedCanFrame
from e87canbus.service import ControllerService, ControllerWorkUnavailable
from e87canbus.simulation.runtime import SimulatedControllerRuntime


def activate_simulation_devices(service: ControllerService) -> None:
    """Inject encoded registry frames for tests that exercise device-gated work."""

    runtime = cast(SimulatedControllerRuntime, service._runtime)
    ids = runtime.config.custom_can_ids
    now = runtime._clock()
    roles = (
        (ids.button_pad_hello, ids.button_pad_heartbeat),
        (ids.servotronic_controller_hello, ids.servotronic_controller_heartbeat),
    )
    for index, (hello_id, heartbeat_id) in enumerate(roles):
        if index == 0 and runtime.button_pad_source is DeviceSource.DISABLED:
            continue
        try:
            service.submit(
                ReceivedCanFrame(
                    CanNetwork.KCAN,
                    encode_hello(DeviceHelloPayload(1, 1, 1, 0), hello_id),
                    now,
                )
            ).result(timeout=1.0)
            service.submit(
                ReceivedCanFrame(
                    CanNetwork.KCAN,
                    encode_heartbeat(
                        DeviceHeartbeatPayload(
                            1,
                            1,
                            runtime.kernel.controller_session_id,
                            0,
                            0,
                        ),
                        heartbeat_id,
                    ),
                    now,
                )
            ).result(timeout=1.0)
        except ControllerWorkUnavailable:
            return
        if runtime.kernel.health.fatal:
            return
