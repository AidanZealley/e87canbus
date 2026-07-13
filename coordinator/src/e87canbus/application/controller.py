"""Hardware-independent application state and behavior."""

from __future__ import annotations

from collections.abc import Callable
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
    speed_valid: bool


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
        self._button_handlers: dict[int, Callable[[], tuple[ApplicationOutput, ...]]] = {
            self.STEERING_MODE_BUTTON_INDEX: self._handle_steering_mode_button,
            self.MANUAL_ASSISTANCE_DOWN_BUTTON_INDEX: self._handle_assistance_down_button,
            self.MANUAL_ASSISTANCE_UP_BUTTON_INDEX: self._handle_assistance_up_button,
            self.MAXIMUM_ASSISTANCE_BUTTON_INDEX: self._toggle_maximum_assistance,
        }

    def snapshot(self) -> ApplicationSnapshot:
        return ApplicationSnapshot(
            vehicle_speed_kph=self.state.vehicle_speed_kph,
            steering_mode=self.state.steering_mode,
            manual_assistance_level=self.state.manual_assistance_level,
            maximum_assistance_active=self.state.maximum_assistance_active,
            speed_valid=self.state.speed_valid,
        )

    def handle_event(
        self, event: ApplicationEvent, now: float
    ) -> tuple[ApplicationOutput, ...]:
        if isinstance(event, SpeedUpdateEvent):
            self.state.set_speed(event.speed_kph, now)
            return ()

        if event.state is not ButtonState.PRESSED:
            return ()

        handler = self._button_handlers.get(event.button_index)
        return handler() if handler is not None else ()

    def tick(self, now: float) -> tuple[ApplicationOutput, ...]:
        speed_updated = self.state.speed_updated_monotonic_s
        self.state.speed_valid = (
            speed_updated is not None
            and now - speed_updated <= self.steering_config.speed_timeout_s
        )
        return ()

    def _handle_steering_mode_button(self) -> tuple[ApplicationOutput, ...]:
        if self.state.maximum_assistance_active:
            return ()

        self.state.steering_mode = (
            SteeringMode.MANUAL
            if self.state.steering_mode is SteeringMode.AUTO
            else SteeringMode.AUTO
        )
        return (self._steering_mode_led_command(),)

    def _handle_assistance_down_button(self) -> tuple[ApplicationOutput, ...]:
        if self.state.maximum_assistance_active:
            return self._exit_maximum_assistance_for_manual_control()

        return self._nudge_manual_assistance(-1)

    def _handle_assistance_up_button(self) -> tuple[ApplicationOutput, ...]:
        if self.state.maximum_assistance_active:
            return self._exit_maximum_assistance_for_manual_control()

        return self._nudge_manual_assistance(1)

    def _nudge_manual_assistance(self, delta: int) -> tuple[ApplicationOutput, ...]:
        if self.state.steering_mode is SteeringMode.AUTO:
            self.state.steering_mode = SteeringMode.MANUAL
            return (self._steering_mode_led_command(),)

        self.state.set_manual_assistance_level(
            self.state.manual_assistance_level + delta,
            self.steering_config.manual_level_count,
        )
        return ()

    def _exit_maximum_assistance_for_manual_control(
        self,
    ) -> tuple[ApplicationOutput, ...]:
        self._restore_pre_maximum_assistance_state()
        self.state.steering_mode = SteeringMode.MANUAL
        return (
            self._steering_mode_led_command(),
            self._maximum_assistance_led_command(),
        )

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
