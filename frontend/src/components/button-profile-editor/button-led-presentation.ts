import type { SteeringState } from "@/api/live-contract.gen"
import type { ButtonCommand } from "./types"

export type ButtonLedRgb = readonly [number, number, number]

export type ButtonLedPresentationContext = {
  synchronized: boolean
  steering: SteeringState | null
  servotronicUsable: boolean
}

export type ButtonLedPresentationAdapter = (
  command: ButtonCommand,
  context: ButtonLedPresentationContext
) => ButtonLedRgb

const OFF = [0, 0, 0] as const
const BLUE = [0, 0, 255] as const
const AMBER = [255, 191, 0] as const
const WHITE = [255, 255, 255] as const
const SOFT_WHITE = [8, 8, 8] as const
const SOFT_AMBER = [8, 6, 0] as const

/**
 * Frontend counterpart of the default domain presenter.
 *
 * Keeping this adapter independent from the grid provides the seam for a
 * future authored LED presentation without changing profile editing.
 */
export const derivedButtonLedPresentation: ButtonLedPresentationAdapter = (
  command,
  context
) => {
  if (command === null) return OFF
  if (!context.synchronized || context.steering === null) return SOFT_AMBER

  switch (command.type) {
    case "select_steering_mode":
    case "toggle_automatic_assistance":
      if (!context.servotronicUsable) return SOFT_AMBER
      return context.steering.mode === "auto" ? BLUE : AMBER
    case "set_maximum_assistance":
    case "toggle_maximum_assistance":
      if (context.steering.maximum_assistance_active) return WHITE
      return context.servotronicUsable ? SOFT_WHITE : SOFT_AMBER
    case "adjust_manual_assistance":
    case "set_manual_assistance_level":
      return context.servotronicUsable ? SOFT_WHITE : SOFT_AMBER
    case "start_high_beam_strobe":
      return SOFT_WHITE
  }
}

export const deriveButtonProfileLedPreview = (
  slots: readonly ButtonCommand[],
  context: ButtonLedPresentationContext,
  presenter: ButtonLedPresentationAdapter = derivedButtonLedPresentation
): ButtonLedRgb[] => slots.map((command) => presenter(command, context))
