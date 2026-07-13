"""Stateful controller for the browser simulator workbench."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from e87canbus.application.controller import ApplicationController, ApplicationSnapshot
from e87canbus.config import AppConfig, CanNetwork, CanNetworkConfig, CustomCanIds, default_config
from e87canbus.protocol.can import (
    LED_AMBER,
    LED_BLUE,
    LED_GREEN,
    LED_OFF,
    LED_RED,
    LED_WHITE,
    LedUpdatePayload,
)
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.runtime import CoordinatorRuntime
from e87canbus.simulation.bus import InMemoryCanTopology, SimulatedCanTraceEntry
from e87canbus.simulation.devices import (
    SimulatedCar,
    SimulatedNeoTrellisNode,
    SimulatedSteeringControllerNode,
)

LED_COLOUR_NAMES = {
    LED_OFF: "off",
    LED_RED: "red",
    LED_GREEN: "green",
    LED_BLUE: "blue",
    LED_AMBER: "amber",
    LED_WHITE: "white",
}


@dataclass(frozen=True)
class SimulatedNetworkStatus:
    config: CanNetworkConfig
    connected: bool
    nodes: tuple[str, ...]


@dataclass(frozen=True)
class SimulatorSnapshot:
    application: ApplicationSnapshot
    next_pressed: bool
    led_colours: dict[int, int]
    networks: tuple[SimulatedNetworkStatus, ...]
    trace: tuple[SimulatedCanTraceEntry, ...]


def trace_entry_to_event(entry: SimulatedCanTraceEntry) -> dict[str, Any]:
    return {
        "type": "frame",
        "sequence": entry.sequence,
        "network": entry.network.value,
        "source": entry.source,
        "arbitration_id": entry.frame.arbitration_id,
        "arbitration_id_hex": f"0x{entry.frame.arbitration_id:x}",
        "data_hex": entry.frame.data.hex(),
        "is_extended_id": entry.frame.is_extended_id,
        "monotonic_s": entry.monotonic_s,
    }


def led_update_to_event(update: LedUpdatePayload) -> dict[str, Any]:
    return {
        "type": "led_update",
        "button_index": update.button_index,
        "colour_code": update.colour_code,
        "colour_name": LED_COLOUR_NAMES.get(update.colour_code, f"unknown-{update.colour_code}"),
    }


def network_status_to_dict(status: SimulatedNetworkStatus) -> dict[str, Any]:
    return {
        "id": status.config.network.value,
        "label": status.config.label,
        "interface": status.config.interface,
        "bitrate": status.config.bitrate,
        "connected": status.connected,
        "nodes": list(status.nodes),
    }


def snapshot_to_dict(snapshot: SimulatorSnapshot) -> dict[str, Any]:
    return {
        "application": {
            "vehicle_speed_kph": snapshot.application.vehicle_speed_kph,
            "steering_mode": snapshot.application.steering_mode.value,
            "manual_assistance_level": snapshot.application.manual_assistance_level,
            "maximum_assistance_active": snapshot.application.maximum_assistance_active,
            "strobe_active": snapshot.application.strobe_active,
        },
        "next_pressed": snapshot.next_pressed,
        "led_colours": snapshot.led_colours,
        "networks": [network_status_to_dict(status) for status in snapshot.networks],
        "trace": [trace_entry_to_event(entry) for entry in snapshot.trace],
    }


def snapshot_event(snapshot: SimulatorSnapshot) -> dict[str, Any]:
    return {"type": "snapshot", "snapshot": snapshot_to_dict(snapshot)}


class SimulatorController:
    def __init__(
        self,
        ids: CustomCanIds | None = None,
        button_count: int = 16,
        *,
        config: AppConfig | None = None,
    ) -> None:
        if button_count < 1 or button_count > 256:
            raise ValueError("button_count must be between 1 and 256")
        self.config = config or default_config()
        if ids is not None:
            self.config = replace(self.config, custom_can_ids=ids)
        self.ids = self.config.custom_can_ids
        self.button_count = button_count
        self._build_session()
        self._button_pressed: dict[int, bool] = {}
        self.last_events: tuple[dict[str, Any], ...] = ()

    def snapshot(self) -> SimulatorSnapshot:
        return SimulatorSnapshot(
            application=self.application.snapshot(),
            next_pressed=self.neotrellis.next_pressed,
            led_colours=dict(self.neotrellis.led_colours),
            networks=tuple(
                SimulatedNetworkStatus(
                    config=network_config,
                    connected=network_config.network in self.pi_buses,
                    nodes=self.topology.nodes(network_config.network),
                )
                for network_config in self.config.can_networks
            ),
            trace=self.topology.trace(),
        )

    def reset(self) -> SimulatorSnapshot:
        self._build_session()
        self._button_pressed = {}
        snapshot = self.snapshot()
        self.last_events = (snapshot_event(snapshot),)
        return snapshot

    def press_button(self, button_index: int) -> SimulatorSnapshot:
        return self._send_button(button_index, pressed=True)

    def release_button(self, button_index: int) -> SimulatorSnapshot:
        return self._send_button(button_index, pressed=False)

    def step_auto(self, button_index: int = 0) -> SimulatorSnapshot:
        self._validate_button_index(button_index)
        self.neotrellis.button_index = button_index
        before_sequence = self.topology.latest_sequence
        sent = self.neotrellis.send_next_button_event()
        self._button_pressed[button_index] = bool(sent.data[1])
        return self._process_pending(before_sequence)

    def _build_session(self) -> None:
        self.topology = InMemoryCanTopology(
            trace_capacity=self.config.simulation.trace_capacity
        )
        enabled = tuple(item for item in self.config.can_networks if item.enabled)

        self.pi_buses = {
            item.network: self.topology.create_bus(item.network, "pi") for item in enabled
        }
        car_buses = {
            item.network: self.topology.create_bus(item.network, "simulated-car")
            for item in self.config.can_networks
        }
        self.car = SimulatedCar(car_buses)

        self.neotrellis = SimulatedNeoTrellisNode(
            bus=self.topology.create_bus(CanNetwork.KCAN, "neotrellis"),
            ids=self.ids,
        )
        self.steering_controller = SimulatedSteeringControllerNode(
            bus=self.topology.create_bus(CanNetwork.KCAN, "steering-controller")
        )

        self.application = ApplicationController(steering_config=self.config.steering)
        self.runtime = CoordinatorRuntime(
            buses=self.pi_buses,
            application=self.application,
            router=ProtocolRouter(self.ids),
        )

        # Compatibility aliases for the established single-bus simulator helpers.
        self.network = self.topology.network(CanNetwork.KCAN)
        self.pi_bus = self.pi_buses.get(CanNetwork.KCAN)

        self.runtime.start()
        self.neotrellis.process_pending_led_updates()
        self.steering_controller.drain_pending()
        self.car.drain_pending()
        self.topology.clear_trace()

    def _send_button(self, button_index: int, pressed: bool) -> SimulatorSnapshot:
        self._validate_button_index(button_index)
        before_sequence = self.topology.latest_sequence
        self.neotrellis.send_button_event(button_index, pressed)
        self._button_pressed[button_index] = pressed
        self.neotrellis.next_pressed = not pressed
        return self._process_pending(before_sequence)

    def _process_pending(self, before_sequence: int) -> SimulatorSnapshot:
        self.runtime.drain_pending()
        updates = self.neotrellis.process_pending_led_updates()
        self.steering_controller.drain_pending()
        self.car.drain_pending()

        snapshot = self.snapshot()
        new_trace = tuple(
            entry for entry in self.topology.trace() if entry.sequence > before_sequence
        )
        events = [snapshot_event(snapshot)]
        events.extend(trace_entry_to_event(entry) for entry in new_trace)
        events.extend(led_update_to_event(update) for update in updates)
        self.last_events = tuple(events)
        return snapshot

    def _validate_button_index(self, button_index: int) -> None:
        if not 0 <= button_index < self.button_count:
            raise ValueError(f"button_index must be between 0 and {self.button_count - 1}")
