"""Stateful controller for the browser simulator workbench."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from e87canbus.application.controller import ApplicationController, ApplicationSnapshot
from e87canbus.application.events import ButtonState, NeoTrellisButtonEvent
from e87canbus.config import CustomCanIds
from e87canbus.protocol.can import (
    LED_AMBER,
    LED_BLUE,
    LED_GREEN,
    LED_OFF,
    LED_RED,
    LED_WHITE,
    LedUpdatePayload,
    decode_button_event,
    encode_button_led_command,
)
from e87canbus.simulation.bus import InMemoryCanNetwork, SimulatedCanTraceEntry
from e87canbus.simulation.devices import SimulatedNeoTrellisNode

LED_COLOUR_NAMES = {
    LED_OFF: "off",
    LED_RED: "red",
    LED_GREEN: "green",
    LED_BLUE: "blue",
    LED_AMBER: "amber",
    LED_WHITE: "white",
}


@dataclass(frozen=True)
class SimulatorSnapshot:
    application: ApplicationSnapshot
    next_pressed: bool
    led_colours: dict[int, int]
    trace: tuple[SimulatedCanTraceEntry, ...]


def trace_entry_to_event(entry: SimulatedCanTraceEntry) -> dict[str, Any]:
    return {
        "type": "frame",
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
        "trace": [trace_entry_to_event(entry) for entry in snapshot.trace],
    }


def snapshot_event(snapshot: SimulatorSnapshot) -> dict[str, Any]:
    return {"type": "snapshot", "snapshot": snapshot_to_dict(snapshot)}


class SimulatorController:
    def __init__(self, ids: CustomCanIds | None = None, button_count: int = 16) -> None:
        if button_count < 1 or button_count > 256:
            raise ValueError("button_count must be between 1 and 256")
        self.ids = ids or CustomCanIds()
        self.button_count = button_count
        self._build_session()
        self._button_pressed: dict[int, bool] = {}
        self.last_events: tuple[dict[str, Any], ...] = ()

    def snapshot(self) -> SimulatorSnapshot:
        return SimulatorSnapshot(
            application=self.application.snapshot(),
            next_pressed=self.neotrellis.next_pressed,
            led_colours=dict(self.neotrellis.led_colours),
            trace=self.network.trace(),
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
        before_count = len(self.network.trace())
        sent = self.neotrellis.send_next_button_event()
        self._button_pressed[button_index] = bool(sent.data[1])
        return self._route_pending_pi_frame(before_count)

    def _build_session(self) -> None:
        self.network = InMemoryCanNetwork()
        self.pi_bus = self.network.create_bus("pi")
        self.application = ApplicationController()
        self.neotrellis = SimulatedNeoTrellisNode(
            bus=self.network.create_bus("neotrellis"),
            ids=self.ids,
        )
        for command in self.application.desired_outputs():
            self.pi_bus.send(encode_button_led_command(command, self.ids))
        self.neotrellis.process_pending_led_updates()
        self.network.clear_trace()

    def _send_button(self, button_index: int, pressed: bool) -> SimulatorSnapshot:
        self._validate_button_index(button_index)
        before_count = len(self.network.trace())
        self.neotrellis.send_button_event(button_index, pressed)
        self._button_pressed[button_index] = pressed
        self.neotrellis.next_pressed = not pressed
        return self._route_pending_pi_frame(before_count)

    def _route_pending_pi_frame(self, before_count: int) -> SimulatorSnapshot:
        while True:
            frame = self.pi_bus.receive(timeout_s=0)
            if frame is None:
                break
            try:
                payload = decode_button_event(frame, self.ids)
            except ValueError:
                continue
            if payload is None:
                continue
            event = NeoTrellisButtonEvent(
                button_index=payload.button_index,
                state=ButtonState.PRESSED if payload.pressed else ButtonState.RELEASED,
            )
            for command in self.application.handle_event(event):
                self.pi_bus.send(encode_button_led_command(command, self.ids))

        updates = self.neotrellis.process_pending_led_updates()
        snapshot = self.snapshot()
        new_trace = self.network.trace()[before_count:]
        events = [snapshot_event(snapshot)]
        events.extend(trace_entry_to_event(entry) for entry in new_trace)
        events.extend(led_update_to_event(update) for update in updates)
        self.last_events = tuple(events)
        return snapshot

    def _validate_button_index(self, button_index: int) -> None:
        if not 0 <= button_index < self.button_count:
            raise ValueError(f"button_index must be between 0 and {self.button_count - 1}")
