/**
 * Mirror of `coordinator/src/e87canbus/domain/controller/button_leds.py`
 * (`derived_button_led_state`), duplicated here rather than served because the
 * editor must preview a DRAFT profile that is not active and no endpoint can
 * derive colours for one. The two implementations must be changed together;
 * `button-led-presentation.test.ts` pins the RGB constants so a backend colour
 * change fails here loudly.
 */
import type { SteeringState } from "@/api/live-contract.gen"
import type { ButtonCommand, ButtonCommandSlot } from "./types"

export type ButtonLedRgb = readonly [number, number, number]

export type ButtonLedPresentationContext = {
  synchronized: boolean
  steering: SteeringState | null
  servotronicUsable: boolean
}

export type ButtonLedPresentationAdapter = (
  slot: ButtonCommandSlot,
  context: ButtonLedPresentationContext
) => ButtonLedRgb

/** Keyed by the backend constant name each colour is copied from. */
export const BUTTON_LED_RGB = {
  RGB_OFF: [0, 0, 0],
  SOFT_AMBER: [8, 6, 0],
} as const satisfies Record<string, ButtonLedRgb>

const { RGB_OFF: OFF, SOFT_AMBER } = BUTTON_LED_RGB
const RESTING_BRIGHTNESS = 8

const commandRequiresServotronic = (
  command: NonNullable<ButtonCommand>
): boolean => command.type !== "start_high_beam_strobe"

const currentMode = (steering: SteeringState): "auto" | "manual" =>
  steering.maximum_assistance_active ? "manual" : steering.mode

export type ButtonVisualState =
  "unassigned" | "unavailable" | "active" | "inactive"

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
    case "start_high_beam_strobe":
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
  if (
    !context.synchronized ||
    (commandRequiresServotronic(slot.command) && !context.servotronicUsable)
  )
    return "unavailable"
  return commandIsActive(slot.command, context.steering) ? "active" : "inactive"
}

/**
 * Frontend counterpart of the default domain presenter.
 *
 * Keeping this adapter independent from the grid provides the seam for a
 * future authored LED presentation without changing profile editing.
 */
export const derivedButtonLedPresentation: ButtonLedPresentationAdapter = (
  slot,
  context
) => {
  switch (deriveButtonVisualState(slot, context)) {
    case "unassigned":
      return OFF
    case "unavailable":
      return SOFT_AMBER
    case "inactive":
      return restingButtonLedRgb(slot!.colour)
    case "active":
      // Animations deliberately preview as their steady full-brightness colour.
      // Preview animation belongs with the workstream 2 animation controls.
      return slot!.active_colour ?? slot!.colour
  }
}

export const deriveButtonProfileLedPreview = (
  slots: readonly ButtonCommandSlot[],
  context: ButtonLedPresentationContext,
  presenter: ButtonLedPresentationAdapter = derivedButtonLedPresentation
): ButtonLedRgb[] => slots.map((slot) => presenter(slot, context))
