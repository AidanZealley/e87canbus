import re
from pathlib import Path

FIRMWARE_SOURCE = (
    Path(__file__).resolve().parents[2] / "devices" / "button-pad" / "src" / "main.cpp"
)


def test_local_fault_controller_lease_expiry_resumes_discovery() -> None:
    source = FIRMWARE_SOURCE.read_text()

    assert re.search(
        r"if \(\(state == DeviceState::OPERATIONAL \|\| "
        r"state == DeviceState::LOCAL_FAULT\) &&\s+"
        r"\(!freshControllerLease\(now\).*?"
        r"beginDiscovery\(now, DeviceState::CONTROLLER_LOST\);",
        source,
        re.DOTALL,
    )


def test_local_fault_recovery_keeps_fault_status_after_controller_rediscovery() -> None:
    source = FIRMWARE_SOURCE.read_text()

    assert re.search(
        r"if \(deviceStatusCode == 0\) \{\s+"
        r"transitionTo\(DeviceState::OPERATIONAL\);.*?"
        r"\} else \{\s+"
        r"transitionTo\(DeviceState::LOCAL_FAULT\);",
        source,
        re.DOTALL,
    )
