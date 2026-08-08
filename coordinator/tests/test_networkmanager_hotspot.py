from __future__ import annotations

import json
import subprocess
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass

import pytest
from e87canbus.adapters.networkmanager_hotspot import (
    RETAINED_DIAGNOSTIC_LIMIT,
    CommandResult,
    NetworkManagerHotspot,
    NetworkManagerHotspotError,
    run_command,
)
from e87canbus.local_controls.model import (
    HotspotAdapterFailed,
    HotspotLifecycle,
    HotspotObserved,
    LocalControlsEvent,
    PanelDisplayState,
)
from e87canbus.local_controls.ports import LocalControlsInputSink
from e87canbus.local_controls.service import LocalControlsLifecycle, LocalControlsService

CONNECTION_UUID = "9e7c46e1-ce27-4012-871a-b4b76bf2eb66"
INTERFACE = "wlan0"
SUBNET = "192.168.87.0/24"


@dataclass
class FakeNetworkManager:
    state: str = "deactivated"
    neighbours: list[object] | None = None
    fail_action: str | None = None

    def __post_init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def __call__(self, argv: Sequence[str]) -> CommandResult:
        command = tuple(argv)
        self.commands.append(command)
        if self.fail_action is not None and self.fail_action in command:
            return CommandResult(10, "", f"simulated {self.fail_action} failure")
        if "GENERAL.STATE" in command:
            return CommandResult(0, f"{self.state}\n", "")
        if command[:2] == ("ip", "-json"):
            return CommandResult(0, json.dumps(self.neighbours or []), "")
        if "up" in command:
            self.state = "activating"
        elif "down" in command:
            self.state = "deactivating"
        return CommandResult(0, "", "")


def make_hotspot(runner: FakeNetworkManager) -> NetworkManagerHotspot:
    return NetworkManagerHotspot(
        connection_uuid=CONNECTION_UUID,
        interface=INTERFACE,
        subnet=SUBNET,
        runner=runner,
    )


def test_start_forces_only_the_predefined_connection_off() -> None:
    runner = FakeNetworkManager(state="activated")
    events: list[LocalControlsEvent] = []
    hotspot = make_hotspot(runner)

    hotspot.start(lambda event: events.append(event) is None)

    assert runner.commands == [
        (
            "nmcli",
            "--terse",
            "--get-values",
            "GENERAL.STATE",
            "connection",
            "show",
            "uuid",
            CONNECTION_UUID,
        ),
        (
            "nmcli",
            "--wait",
            "0",
            "connection",
            "down",
            "uuid",
            CONNECTION_UUID,
        ),
    ]
    assert events == []


def test_active_observation_requires_a_valid_neighbour_in_the_configured_subnet() -> None:
    runner = FakeNetworkManager(state="deactivated")
    events: list[LocalControlsEvent] = []
    hotspot = make_hotspot(runner)
    hotspot.start(lambda event: events.append(event) is None)
    runner.commands.clear()

    hotspot.activate()
    assert events == []
    runner.state = "activated"
    runner.neighbours = [
        {
            "dst": "192.168.87.12",
            "dev": INTERFACE,
            "lladdr": "02:00:00:00:00:12",
            "state": ["FAILED"],
        },
        {
            "dst": "192.168.88.13",
            "dev": INTERFACE,
            "lladdr": "02:00:00:00:00:13",
            "state": ["REACHABLE"],
        },
        {
            "dst": "192.168.87.14",
            "dev": INTERFACE,
            "lladdr": "02:00:00:00:00:14",
            "state": ["STALE"],
        },
    ]

    hotspot.poll(1.0)

    assert events == [HotspotObserved(HotspotLifecycle.ACTIVE, client_connected=True)]
    assert runner.commands[0] == (
        "nmcli",
        "--wait",
        "0",
        "connection",
        "up",
        "uuid",
        CONNECTION_UUID,
        "ifname",
        INTERFACE,
    )
    assert runner.commands[-1] == (
        "ip",
        "-json",
        "-4",
        "neighbour",
        "show",
        "dev",
        INTERFACE,
    )


@pytest.mark.parametrize(
    ("networkmanager_state", "expected"),
    [
        ("", HotspotLifecycle.DISABLED),
        ("deactivated", HotspotLifecycle.DISABLED),
        ("activating", HotspotLifecycle.ACTIVATING),
        ("activated", HotspotLifecycle.ACTIVE),
        ("deactivating", HotspotLifecycle.DEACTIVATING),
        ("failed", HotspotLifecycle.FAULT),
    ],
)
def test_poll_reports_each_networkmanager_lifecycle(
    networkmanager_state: str,
    expected: HotspotLifecycle,
) -> None:
    runner = FakeNetworkManager(state="deactivated")
    events: list[LocalControlsEvent] = []
    hotspot = make_hotspot(runner)
    hotspot.start(lambda event: events.append(event) is None)
    if expected in {HotspotLifecycle.ACTIVATING, HotspotLifecycle.ACTIVE}:
        hotspot.activate()
    runner.state = networkmanager_state

    hotspot.poll(1.0)

    assert events == [HotspotObserved(expected)]


def test_unexpected_inactive_profile_converges_to_shared_fault() -> None:
    runner = FakeNetworkManager(state="deactivated")
    events: list[LocalControlsEvent] = []
    hotspot = make_hotspot(runner)
    hotspot.start(lambda event: events.append(event) is None)
    hotspot.activate()
    runner.state = ""

    hotspot.poll(1.0)

    assert events == [HotspotAdapterFailed("managed hotspot became inactive unexpectedly")]


def test_poll_throttles_external_process_observations() -> None:
    runner = FakeNetworkManager(state="deactivated")
    hotspot = make_hotspot(runner)
    hotspot.start(lambda event: True)
    runner.commands.clear()

    hotspot.poll(1.0)
    hotspot.poll(1.05)
    hotspot.poll(1.24)
    hotspot.poll(1.25)

    assert len(runner.commands) == 2


def test_failed_activation_does_not_retry_or_publish_optimistic_active_state() -> None:
    runner = FakeNetworkManager(state="deactivated", fail_action="up")
    events: list[LocalControlsEvent] = []
    hotspot = make_hotspot(runner)
    hotspot.start(lambda event: events.append(event) is None)

    with pytest.raises(NetworkManagerHotspotError, match="could not activate hotspot"):
        hotspot.activate()
    hotspot.poll(1.0)

    assert events == [HotspotObserved(HotspotLifecycle.DISABLED)]
    assert sum("up" in command for command in runner.commands) == 1


def test_startup_failure_uses_the_shared_hotspot_failure_event_and_retries_off() -> None:
    runner = FakeNetworkManager(state="activated", fail_action="down")
    events: list[LocalControlsEvent] = []
    hotspot = make_hotspot(runner)
    hotspot.start(lambda event: events.append(event) is None)

    assert events == [HotspotAdapterFailed("could not deactivate hotspot: simulated down failure")]

    runner.fail_action = None
    hotspot.poll(1.0)

    assert runner.state == "deactivating"
    assert events == [HotspotAdapterFailed("could not deactivate hotspot: simulated down failure")]

    hotspot.poll(1.25)

    assert events[-1] == HotspotObserved(HotspotLifecycle.DEACTIVATING)


def test_configuration_rejects_arguments_that_could_expand_command_scope() -> None:
    runner = FakeNetworkManager()
    with pytest.raises(ValueError, match="badly formed hexadecimal UUID"):
        NetworkManagerHotspot(
            connection_uuid="not-a-uuid",
            interface=INTERFACE,
            subnet=SUBNET,
            runner=runner,
        )
    with pytest.raises(ValueError, match="single non-option name"):
        NetworkManagerHotspot(
            connection_uuid=CONNECTION_UUID,
            interface="--ask",
            subnet=SUBNET,
            runner=runner,
        )


def test_close_makes_one_unconditional_best_effort_deactivation() -> None:
    runner = FakeNetworkManager(state="deactivated", fail_action="down")
    hotspot = make_hotspot(runner)
    hotspot.start(lambda event: True)
    runner.commands.clear()

    hotspot.close()

    assert runner.commands == [
        (
            "nmcli",
            "--wait",
            "0",
            "connection",
            "down",
            "uuid",
            CONNECTION_UUID,
        )
    ]


class BlockingShutdownRunner:
    """Hold each command in the maximum poll-plus-close shutdown path."""

    def __init__(self) -> None:
        self.armed = threading.Event()
        self.inspect_started = threading.Event()
        self.release_inspect = threading.Event()
        self.poll_down_started = threading.Event()
        self.release_poll_down = threading.Event()
        self.close_down_started = threading.Event()
        self.release_close_down = threading.Event()
        self.sequence: list[str] = []
        self._down_count = 0

    def __call__(self, argv: Sequence[str]) -> CommandResult:
        command = tuple(argv)
        if "GENERAL.STATE" in command:
            if not self.armed.is_set():
                return CommandResult(0, "deactivated\n", "")
            self.sequence.append("inspect")
            self.inspect_started.set()
            assert self.release_inspect.wait(timeout=1.0)
            return CommandResult(0, "activated\n", "")
        if "down" in command:
            self._down_count += 1
            if not self.armed.is_set():
                return CommandResult(0, "", "")
            if self._down_count == 1:
                self.sequence.append("poll down")
                self.poll_down_started.set()
                assert self.release_poll_down.wait(timeout=1.0)
            else:
                self.sequence.append("close down")
                self.close_down_started.set()
                assert self.release_close_down.wait(timeout=1.0)
            return CommandResult(0, "", "")
        raise AssertionError(f"unexpected command: {command}")


class NullPanel:
    def start(self, submit: LocalControlsInputSink) -> None:
        del submit

    def set_display(self, display: PanelDisplayState) -> None:
        del display

    def poll(self, now: float) -> None:
        del now

    def close(self) -> None:
        pass


class NullCondition:
    def start(self, submit: LocalControlsInputSink) -> None:
        del submit

    def poll(self, now: float) -> None:
        del now

    def close(self) -> None:
        pass


def test_service_stop_completes_during_maximum_hotspot_poll_sequence() -> None:
    runner = BlockingShutdownRunner()
    hotspot = NetworkManagerHotspot(
        connection_uuid=CONNECTION_UUID,
        interface=INTERFACE,
        subnet=SUBNET,
        runner=runner,
        observation_interval_s=0.005,
    )
    service = LocalControlsService(
        panel=NullPanel(),
        hotspot=hotspot,
        coordinator_condition=NullCondition(),
        poll_interval_s=0.005,
        panel_refresh_interval_s=10.0,
    )
    service.start()
    runner.armed.set()
    assert runner.inspect_started.wait(timeout=1.0)

    failures: list[BaseException] = []

    def stop_service() -> None:
        try:
            service.stop()
        except BaseException as exc:
            failures.append(exc)

    started_at = time.monotonic()
    stop_thread = threading.Thread(target=stop_service)
    stop_thread.start()
    runner.release_inspect.set()
    assert runner.poll_down_started.wait(timeout=1.0)
    runner.release_poll_down.set()
    assert runner.close_down_started.wait(timeout=1.0)
    runner.release_close_down.set()
    stop_thread.join(timeout=2.0)

    assert not stop_thread.is_alive()
    assert not failures
    assert time.monotonic() - started_at < 5.0
    assert service.lifecycle is LocalControlsLifecycle.STOPPED
    assert runner.sequence == ["inspect", "poll down", "close down"]


def test_default_runner_retains_bounded_diagnostics_and_never_invokes_a_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_run(argv: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["argv"] = argv
        observed.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "x" * 5000, "y" * 5000)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_command(("nmcli", "general", "status"))

    assert observed["argv"] == ("nmcli", "general", "status")
    assert "shell" not in observed
    assert observed["timeout"] == 1.0
    assert len(result.stdout) == RETAINED_DIAGNOSTIC_LIMIT
    assert len(result.stderr) == RETAINED_DIAGNOSTIC_LIMIT
