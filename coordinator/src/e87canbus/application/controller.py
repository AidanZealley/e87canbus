"""Hardware-independent application state and behavior."""

from __future__ import annotations

from dataclasses import dataclass, replace

from e87canbus.application.events import (
    ButtonLedCommand,
    ButtonState,
    LedColour,
    NeoTrellisButtonEvent,
    SpeedUpdateEvent,
    SteeringMode,
)
from e87canbus.application.state import (
    ApplicationState,
    MaximumAssistance,
    SpeedSample,
)
from e87canbus.config import SteeringConfig
from e87canbus.features.steering import clamp_manual_level


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
        state: ApplicationState | None = None,
        steering_config: SteeringConfig | None = None,
    ) -> None:
        self.steering_config = steering_config or SteeringConfig()
        self.state = self._normalized_state(state or ApplicationState())

    def snapshot(self) -> ApplicationSnapshot:
        mode, manual_level, maximum_active = self._steering_projection()
        sample = self.state.speed_sample
        return ApplicationSnapshot(
            vehicle_speed_kph=sample.speed_kph if sample is not None else 0.0,
            steering_mode=mode,
            manual_assistance_level=manual_level,
            maximum_assistance_active=maximum_active,
            speed_valid=(
                sample is not None
                and self.state.speed_evaluated_at - sample.observed_at
                <= self.steering_config.speed_timeout_s
            ),
        )

    def handle_event(
        self, event: ApplicationEvent, now: float
    ) -> tuple[ApplicationOutput, ...]:
        if isinstance(event, SpeedUpdateEvent):
            self.state = replace(
                self.state,
                speed_sample=SpeedSample(
                    speed_kph=max(0.0, event.speed_kph),
                    observed_at=now,
                    source_network=event.source_network,
                ),
                speed_evaluated_at=now,
            )
            return ()

        if event.state is not ButtonState.PRESSED:
            return ()

        match event.button_index:
            case self.STEERING_MODE_BUTTON_INDEX:
                return self._toggle_steering_mode()
            case self.MANUAL_ASSISTANCE_DOWN_BUTTON_INDEX:
                return self._adjust_assistance(-1)
            case self.MANUAL_ASSISTANCE_UP_BUTTON_INDEX:
                return self._adjust_assistance(1)
            case self.MAXIMUM_ASSISTANCE_BUTTON_INDEX:
                return self._toggle_maximum_assistance()
            case _:
                return ()

    def tick(self, now: float) -> tuple[ApplicationOutput, ...]:
        self.state = replace(self.state, speed_evaluated_at=now)
        return ()

    def desired_outputs(self) -> tuple[ApplicationOutput, ...]:
        """Return a full output snapshot for startup and reconnection."""
        return (
            self._steering_mode_led_command(),
            self._maximum_assistance_led_command(),
        )

    def _toggle_steering_mode(self) -> tuple[ApplicationOutput, ...]:
        steering = self.state.steering
        if isinstance(steering, MaximumAssistance):
            return ()

        mode = (
            SteeringMode.MANUAL
            if steering.mode is SteeringMode.AUTO
            else SteeringMode.AUTO
        )
        self.state = replace(self.state, steering=replace(steering, mode=mode))
        return (self._steering_mode_led_command(),)

    def _adjust_assistance(self, delta: int) -> tuple[ApplicationOutput, ...]:
        steering = self.state.steering
        if isinstance(steering, MaximumAssistance):
            self.state = replace(
                self.state,
                steering=replace(steering.previous, mode=SteeringMode.MANUAL),
            )
            return (
                self._steering_mode_led_command(),
                self._maximum_assistance_led_command(),
            )

        if steering.mode is SteeringMode.AUTO:
            self.state = replace(
                self.state,
                steering=replace(steering, mode=SteeringMode.MANUAL),
            )
            return (self._steering_mode_led_command(),)

        manual_level = clamp_manual_level(
            steering.manual_level + delta,
            self.steering_config.manual_level_count,
        )
        self.state = replace(
            self.state,
            steering=replace(steering, manual_level=manual_level),
        )
        return ()

    def _toggle_maximum_assistance(self) -> tuple[ButtonLedCommand, ...]:
        steering = self.state.steering
        self.state = replace(
            self.state,
            steering=(
                steering.previous
                if isinstance(steering, MaximumAssistance)
                else MaximumAssistance(previous=steering)
            ),
        )
        return (
            self._steering_mode_led_command(),
            self._maximum_assistance_led_command(),
        )

    def _steering_projection(self) -> tuple[SteeringMode, int, bool]:
        steering = self.state.steering
        if isinstance(steering, MaximumAssistance):
            return (
                SteeringMode.MANUAL,
                self.steering_config.manual_level_count - 1,
                True,
            )
        return steering.mode, steering.manual_level, False

    def _steering_mode_led_command(self) -> ButtonLedCommand:
        mode, _, _ = self._steering_projection()
        return ButtonLedCommand(
            button_index=self.STEERING_MODE_BUTTON_INDEX,
            colour=LedColour.BLUE if mode is SteeringMode.AUTO else LedColour.AMBER,
        )

    def _maximum_assistance_led_command(self) -> ButtonLedCommand:
        return ButtonLedCommand(
            button_index=self.MAXIMUM_ASSISTANCE_BUTTON_INDEX,
            colour=(
                LedColour.WHITE
                if isinstance(self.state.steering, MaximumAssistance)
                else LedColour.OFF
            ),
        )

    def _normalized_state(self, state: ApplicationState) -> ApplicationState:
        steering = state.steering
        normal = steering.previous if isinstance(steering, MaximumAssistance) else steering
        normal = replace(
            normal,
            manual_level=clamp_manual_level(
                normal.manual_level,
                self.steering_config.manual_level_count,
            ),
        )
        return replace(
            state,
            steering=(
                MaximumAssistance(previous=normal)
                if isinstance(steering, MaximumAssistance)
                else normal
            ),
        )
