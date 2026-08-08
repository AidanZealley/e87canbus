"""Narrow NetworkManager boundary for the coordinator's predefined hotspot."""

from __future__ import annotations

import ipaddress
import json
import os
import subprocess
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from e87canbus.local_controls.model import (
    HotspotAdapterFailed,
    HotspotLifecycle,
    HotspotObserved,
)
from e87canbus.local_controls.ports import LocalControlsInputSink

COMMAND_TIMEOUT_S = 1.0
RETAINED_DIAGNOSTIC_LIMIT = 4096
OBSERVATION_INTERVAL_S = 0.25


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def __call__(self, argv: Sequence[str]) -> CommandResult: ...


class NetworkManagerHotspotError(RuntimeError):
    pass


def run_command(argv: Sequence[str]) -> CommandResult:
    """Run one fixed-shape command without a shell, retaining bounded diagnostics."""

    try:
        completed = subprocess.run(
            argv,
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_S,
            env={**os.environ, "LC_ALL": "C"},
        )
    except subprocess.TimeoutExpired as exc:
        raise NetworkManagerHotspotError("hotspot command timed out") from exc
    except OSError as exc:
        raise NetworkManagerHotspotError(f"hotspot command could not run: {exc}") from exc
    return CommandResult(
        completed.returncode,
        completed.stdout[:RETAINED_DIAGNOSTIC_LIMIT],
        completed.stderr[:RETAINED_DIAGNOSTIC_LIMIT],
    )


class NetworkManagerHotspot:
    """Control only one provisioned NetworkManager connection and interface."""

    _VALID_NEIGHBOUR_STATES = frozenset({"REACHABLE", "STALE", "DELAY", "PROBE", "PERMANENT"})

    def __init__(
        self,
        *,
        connection_uuid: str,
        interface: str,
        subnet: str,
        runner: CommandRunner = run_command,
        observation_interval_s: float = OBSERVATION_INTERVAL_S,
    ) -> None:
        self._connection_uuid = str(UUID(connection_uuid))
        if not interface or interface.startswith("-") or any(char.isspace() for char in interface):
            raise ValueError("interface must be a single non-option name")
        self._interface = interface
        self._subnet = ipaddress.ip_network(subnet, strict=False)
        if self._subnet.version != 4:
            raise ValueError("hotspot subnet must be IPv4")
        if observation_interval_s <= 0:
            raise ValueError("observation_interval_s must be positive")
        self._runner = runner
        self._observation_interval_s = observation_interval_s
        self._submit: LocalControlsInputSink | None = None
        self._target_active = False
        self._next_observation_at = 0.0

    def start(self, submit: LocalControlsInputSink) -> None:
        self._submit = submit
        self._target_active = False
        try:
            self._force_target()
        except NetworkManagerHotspotError as exc:
            # Startup has no enclosing effect for the service to translate, so submit the
            # same shared failure event used for later command and inspection failures.
            if not submit(HotspotAdapterFailed(str(exc))):
                raise NetworkManagerHotspotError(
                    "local-controls rejected the startup hotspot failure"
                ) from exc

    def activate(self) -> None:
        self._run_checked(
            "activate hotspot",
            (
                "nmcli",
                "--wait",
                "0",
                "connection",
                "up",
                "uuid",
                self._connection_uuid,
                "ifname",
                self._interface,
            ),
        )
        # Failed activation must leave the safe off target in place. The service owns
        # deciding whether a later button press should request another attempt.
        self._target_active = True
        self._next_observation_at = 0.0

    def deactivate(self) -> None:
        self._target_active = False
        self._deactivate()
        self._next_observation_at = 0.0

    def poll(self, now: float) -> None:
        if now < self._next_observation_at:
            return
        # Failure retries use the same cadence, avoiding a process storm while retaining
        # convergence after transient NetworkManager errors.
        self._next_observation_at = now + self._observation_interval_s
        lifecycle = self._inspect_lifecycle()
        if not self._target_active and lifecycle in {
            HotspotLifecycle.ACTIVATING,
            HotspotLifecycle.ACTIVE,
        }:
            self._deactivate()
            # NetworkManager accepted the safe-off request, but its resulting lifecycle
            # remains an observation for the next cadence rather than a fabricated state.
            return

        if self._target_active and lifecycle is HotspotLifecycle.DISABLED:
            submit = self._submit
            if submit is not None:
                submit(HotspotAdapterFailed("managed hotspot became inactive unexpectedly"))
            return
        client_connected = (
            self._client_connected() if lifecycle is HotspotLifecycle.ACTIVE else False
        )
        submit = self._submit
        if submit is not None:
            submit(HotspotObserved(lifecycle, client_connected))

    def close(self) -> None:
        try:
            self._target_active = False
            # Shutdown has a five-second owner budget. One bounded, asynchronous
            # NetworkManager request is safer than inspecting and conditionally issuing
            # a second process while the service is already stopping.
            with suppress(NetworkManagerHotspotError):
                self._deactivate()
        finally:
            self._submit = None

    def _force_target(self) -> None:
        lifecycle = self._inspect_lifecycle()
        if lifecycle in {HotspotLifecycle.ACTIVATING, HotspotLifecycle.ACTIVE}:
            self._deactivate()

    def _inspect_lifecycle(self) -> HotspotLifecycle:
        result = self._run_checked(
            "inspect hotspot",
            (
                "nmcli",
                "--terse",
                "--get-values",
                "GENERAL.STATE",
                "connection",
                "show",
                "uuid",
                self._connection_uuid,
            ),
        )
        # NetworkManager emits an empty GENERAL.STATE value for an inactive profile on
        # supported Pi versions; some versions spell the same state as "deactivated".
        if not result.stdout.strip():
            return HotspotLifecycle.DISABLED
        lines = result.stdout.strip().casefold().splitlines()
        if len(lines) != 1:
            raise NetworkManagerHotspotError("NetworkManager returned an invalid hotspot state")
        state = lines[0]
        if state.endswith(")") and "(" in state:
            state = state.rsplit("(", 1)[1][:-1]
        states = {
            "deactivated": HotspotLifecycle.DISABLED,
            "activating": HotspotLifecycle.ACTIVATING,
            "activated": HotspotLifecycle.ACTIVE,
            "deactivating": HotspotLifecycle.DEACTIVATING,
            "failed": HotspotLifecycle.FAULT,
            "unknown": HotspotLifecycle.FAULT,
        }
        try:
            return states[state]
        except KeyError as exc:
            raise NetworkManagerHotspotError(
                "NetworkManager returned an unsupported hotspot state"
            ) from exc

    def _deactivate(self) -> None:
        self._run_checked(
            "deactivate hotspot",
            (
                "nmcli",
                "--wait",
                "0",
                "connection",
                "down",
                "uuid",
                self._connection_uuid,
            ),
        )

    def _client_connected(self) -> bool:
        result = self._run_checked(
            "inspect hotspot clients",
            ("ip", "-json", "-4", "neighbour", "show", "dev", self._interface),
        )
        try:
            neighbours = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise NetworkManagerHotspotError("ip returned invalid neighbour data") from exc
        if not isinstance(neighbours, list):
            raise NetworkManagerHotspotError("ip returned invalid neighbour data")
        return any(self._valid_neighbour(neighbour) for neighbour in neighbours)

    def _valid_neighbour(self, neighbour: object) -> bool:
        if not isinstance(neighbour, dict):
            return False
        address_text = neighbour.get("dst")
        link_address = neighbour.get("lladdr")
        states = neighbour.get("state")
        if (
            not isinstance(address_text, str)
            or not isinstance(link_address, str)
            or not link_address
            or not isinstance(states, list)
            or not all(isinstance(state, str) for state in states)
        ):
            return False
        try:
            address = ipaddress.ip_address(address_text)
        except ValueError:
            return False
        return address in self._subnet and bool(self._VALID_NEIGHBOUR_STATES.intersection(states))

    def _run_checked(self, action: str, argv: Sequence[str]) -> CommandResult:
        result = self._runner(argv)
        if result.returncode != 0:
            diagnostic = result.stderr.strip() or result.stdout.strip() or "command failed"
            raise NetworkManagerHotspotError(
                f"could not {action}: {diagnostic[:RETAINED_DIAGNOSTIC_LIMIT]}"
            )
        return result
