import type { ButtonProfileDefinitionRequest } from "@/api/http"

/** Every slot the pad exposes; the API contract accepts nothing shorter or longer. */
export type ButtonCommandSlots = ButtonProfileDefinitionRequest["slots"]
export type ButtonCommand = ButtonCommandSlots[number]

/**
 * Typed against the contract tuple so a backend pad-size change fails the build
 * here rather than at runtime on the first save.
 */
export const BUTTON_SLOT_COUNT: ButtonCommandSlots["length"] = 16

const hasEverySlot = (
  commands: readonly ButtonCommand[]
): commands is ButtonCommandSlots => commands.length === BUTTON_SLOT_COUNT

/**
 * The one place a command list becomes a full slot set, so editing helpers can
 * work with plain arrays without an unchecked cast reaching the save request.
 */
export const toButtonCommandSlots = (
  commands: readonly ButtonCommand[]
): ButtonCommandSlots => {
  if (!hasEverySlot(commands)) {
    throw new RangeError(
      `a button profile needs exactly ${BUTTON_SLOT_COUNT} slots, received ${commands.length}`
    )
  }
  return commands
}

export type ButtonCommandType =
  NonNullable<ButtonCommand>["type"] | "unassigned"

/** Transient values used only while the binding dialog is open. */
export type ButtonCommandFormValue = {
  type: ButtonCommandType
  mode: "auto" | "manual"
  delta: "-1" | "1"
  level: string
  enabled: "true" | "false"
}
