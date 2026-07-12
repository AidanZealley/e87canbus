"""Hardware-independent application state and behavior."""

from __future__ import annotations

from dataclasses import dataclass

from e87canbus.application.events import (
    ButtonLedCommand,
    ButtonState,
    LedColour,
    NeoTrellisButtonEvent,
    SpeedUpdateEvent,
    SteeringMode,
)
from e87canbus.application.state import RuntimeState


@dataclass(frozen=True)
class ApplicationSnapshot:
    vehicle_speed_kph: float
    steering_mode: SteeringMode
    manual_assistance_level: int
    strobe_active: bool


ApplicationEvent = NeoTrellisButtonEvent | SpeedUpdateEvent
ApplicationOutput = ButtonLedCommand


class ApplicationController:
    """Own authoritative application state and turn inputs into desired outputs."""

    STEERING_MODE_BUTTON_INDEX = 0

    def __init__(self, state: RuntimeState | None = None) -> None:
        self.state = state or RuntimeState()

    def snapshot(self) -> ApplicationSnapshot:
        return ApplicationSnapshot(
            vehicle_speed_kph=self.state.vehicle_speed_kph,
            steering_mode=self.state.steering_mode,
            manual_assistance_level=self.state.manual_assistance_level,
            strobe_active=self.state.strobe_active,
        )

    def handle_event(self, event: ApplicationEvent) -> tuple[ApplicationOutput, ...]:
        if isinstance(event, SpeedUpdateEvent):
            self.state.set_speed(event.speed_kph)
            return ()

        if (
            event.button_index == self.STEERING_MODE_BUTTON_INDEX
            and event.state is ButtonState.PRESSED
        ):
            self.state.steering_mode = (
                SteeringMode.MANUAL
                if self.state.steering_mode is SteeringMode.AUTO
                else SteeringMode.AUTO
            )
            return (self._steering_mode_led_command(),)

        return ()

    def desired_outputs(self) -> tuple[ApplicationOutput, ...]:
        """Return a full output snapshot for startup and reconnection."""
        return (self._steering_mode_led_command(),)

    def _steering_mode_led_command(self) -> ButtonLedCommand:
        colour = (
            LedColour.BLUE
            if self.state.steering_mode is SteeringMode.AUTO
            else LedColour.AMBER
        )
        return ButtonLedCommand(
            button_index=self.STEERING_MODE_BUTTON_INDEX,
            colour=colour,
        )
