/** Preview a draft profile using its authored colours and current steering state. */
import type { SteeringState } from "@e87canbus/coordinator-client/api/http/types.gen"
import type { ButtonCommand, ButtonCommandSlot } from "./types"

export type ButtonLedRgb = readonly [number, number, number]

export type ButtonLedPresentationContext = {
  synchronized: boolean
  steering: SteeringState | null
}

export type ButtonLedPresentationAdapter = (
  slot: ButtonCommandSlot,
  context: ButtonLedPresentationContext
) => ButtonLedRgb

/** Preview colour for an unassigned button. */
export const BUTTON_LED_RGB = {
  RGB_OFF: [0, 0, 0],
} as const satisfies Record<string, ButtonLedRgb>

const { RGB_OFF: OFF } = BUTTON_LED_RGB
const RESTING_BRIGHTNESS = 8

const currentMode = (steering: SteeringState): "auto" | "manual" =>
  steering.maximum_assistance_active ? "manual" : steering.mode

export type ButtonVisualState = "unassigned" | "active" | "inactive"

const commandIsActive = (
  command: NonNullable<ButtonCommand>,
  steering: SteeringState | null
): boolean => {
  if (steering === null) return false
  switch (command.type) {
    case "select_steering_mode":
      return currentMode(steering) === command.mode
    case "toggle_automatic_assistance":
      return currentMode(steering) === "auto"
    case "set_manual_assistance_level":
      return (
        !steering.maximum_assistance_active &&
        steering.mode === "manual" &&
        steering.manual_assistance_level === command.level
      )
    case "set_maximum_assistance":
      return steering.maximum_assistance_active === command.enabled
    case "toggle_maximum_assistance":
      return steering.maximum_assistance_active
    case "adjust_manual_assistance":
      return false
  }
}

export const restingButtonLedRgb = (rgb: ButtonLedRgb): ButtonLedRgb => {
  const dim = (channel: number) =>
    Math.floor((channel * RESTING_BRIGHTNESS + 127) / 255)
  return [dim(rgb[0]), dim(rgb[1]), dim(rgb[2])]
}

export const deriveButtonVisualState = (
  slot: ButtonCommandSlot,
  context: ButtonLedPresentationContext
): ButtonVisualState => {
  if (slot === null) return "unassigned"
  if (!context.synchronized || context.steering === null) return "inactive"
  return commandIsActive(slot.command, context.steering) ? "active" : "inactive"
}

/** Resolve a slot's preview colour without sending a device program. */
export const derivedButtonLedPresentation: ButtonLedPresentationAdapter = (
  slot,
  context
) => {
  switch (deriveButtonVisualState(slot, context)) {
    case "unassigned":
      return OFF
    case "inactive":
      return restingButtonLedRgb(slot!.colour)
    case "active":
      // Animations deliberately preview as their steady full-brightness colour.
      return slot!.active_colour ?? slot!.colour
  }
}

export const deriveButtonProfileLedPreview = (
  slots: readonly ButtonCommandSlot[],
  context: ButtonLedPresentationContext,
  presenter: ButtonLedPresentationAdapter = derivedButtonLedPresentation
): ButtonLedRgb[] => slots.map((slot) => presenter(slot, context))
