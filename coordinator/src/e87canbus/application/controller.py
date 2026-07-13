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
from e87canbus.config import SteeringConfig


@dataclass(frozen=True)
class ApplicationSnapshot:
    vehicle_speed_kph: float
    steering_mode: SteeringMode
    manual_assistance_level: int
    maximum_assistance_active: bool


ApplicationEvent = NeoTrellisButtonEvent | SpeedUpdateEvent
ApplicationOutput = ButtonLedCommand


class ApplicationController:
    """Own authoritative application state and turn inputs into desired outputs."""

    STEERING_MODE_BUTTON_INDEX = 0
    MANUAL_ASSISTANCE_DOWN_BUTTON_INDEX = 1
    MANUAL_ASSISTANCE_UP_BUTTON_INDEX = 2
    MAXIMUM_ASSISTANCE_BUTTON_INDEX = 3

    def __init__(
        self,
        state: RuntimeState | None = None,
        steering_config: SteeringConfig | None = None,
    ) -> None:
        self.state = state or RuntimeState()
        self.steering_config = steering_config or SteeringConfig()
        self.state.set_manual_assistance_level(
            self.state.manual_assistance_level,
            self.steering_config.manual_level_count,
        )
        self._pre_maximum_assistance_state: tuple[SteeringMode, int] | None = None

    def snapshot(self) -> ApplicationSnapshot:
        return ApplicationSnapshot(
            vehicle_speed_kph=self.state.vehicle_speed_kph,
            steering_mode=self.state.steering_mode,
            manual_assistance_level=self.state.manual_assistance_level,
            maximum_assistance_active=self.state.maximum_assistance_active,
        )

    def handle_event(self, event: ApplicationEvent) -> tuple[ApplicationOutput, ...]:
        if isinstance(event, SpeedUpdateEvent):
            self.state.set_speed(event.speed_kph)
            return ()

        if event.state is not ButtonState.PRESSED:
            return ()

        if event.button_index == self.MAXIMUM_ASSISTANCE_BUTTON_INDEX:
            return self._toggle_maximum_assistance()

        if self.state.maximum_assistance_active:
            if event.button_index in (
                self.MANUAL_ASSISTANCE_DOWN_BUTTON_INDEX,
                self.MANUAL_ASSISTANCE_UP_BUTTON_INDEX,
            ):
                self._restore_pre_maximum_assistance_state()
                self.state.steering_mode = SteeringMode.MANUAL
                return (
                    self._steering_mode_led_command(),
                    self._maximum_assistance_led_command(),
                )

            # The mode control does not mutate the state that button 4 will restore.
            return ()

        if event.button_index == self.STEERING_MODE_BUTTON_INDEX:
            self.state.steering_mode = (
                SteeringMode.MANUAL
                if self.state.steering_mode is SteeringMode.AUTO
                else SteeringMode.AUTO
            )
            return (self._steering_mode_led_command(),)

        if event.button_index in (
            self.MANUAL_ASSISTANCE_DOWN_BUTTON_INDEX,
            self.MANUAL_ASSISTANCE_UP_BUTTON_INDEX,
        ):
            if self.state.steering_mode is SteeringMode.AUTO:
                self.state.steering_mode = SteeringMode.MANUAL
                return (self._steering_mode_led_command(),)

            delta = (
                -1
                if event.button_index == self.MANUAL_ASSISTANCE_DOWN_BUTTON_INDEX
                else 1
            )
            self.state.set_manual_assistance_level(
                self.state.manual_assistance_level + delta,
                self.steering_config.manual_level_count,
            )

        return ()

    def desired_outputs(self) -> tuple[ApplicationOutput, ...]:
        """Return a full output snapshot for startup and reconnection."""
        return (
            self._steering_mode_led_command(),
            self._maximum_assistance_led_command(),
        )

    def _toggle_maximum_assistance(self) -> tuple[ButtonLedCommand, ...]:
        if self.state.maximum_assistance_active:
            self._restore_pre_maximum_assistance_state()
        else:
            self._pre_maximum_assistance_state = (
                self.state.steering_mode,
                self.state.manual_assistance_level,
            )
            self.state.steering_mode = SteeringMode.MANUAL
            self.state.set_manual_assistance_level(
                self.steering_config.manual_level_count - 1,
                self.steering_config.manual_level_count,
            )
            self.state.maximum_assistance_active = True

        return (
            self._steering_mode_led_command(),
            self._maximum_assistance_led_command(),
        )

    def _restore_pre_maximum_assistance_state(self) -> None:
        assert self._pre_maximum_assistance_state is not None
        mode, manual_level = self._pre_maximum_assistance_state
        self.state.steering_mode = mode
        self.state.set_manual_assistance_level(
            manual_level,
            self.steering_config.manual_level_count,
        )
        self.state.maximum_assistance_active = False
        self._pre_maximum_assistance_state = None

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

    def _maximum_assistance_led_command(self) -> ButtonLedCommand:
        return ButtonLedCommand(
            button_index=self.MAXIMUM_ASSISTANCE_BUTTON_INDEX,
            colour=(
                LedColour.WHITE
                if self.state.maximum_assistance_active
                else LedColour.OFF
            ),
        )
