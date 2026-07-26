import type { ButtonProfileDefinitionResponse } from "@/api/http"

/** Every configurable slot; the API contract accepts nothing shorter or longer. */
export type ButtonCommandSlots = ButtonProfileDefinitionResponse["slots"]
export type ButtonCommandSlot = ButtonCommandSlots[number]
export type ButtonCommand = NonNullable<ButtonCommandSlot>["command"] | null

/**
 * Typed against the contract tuple so a backend pad-size change fails the build
 * here rather than at runtime on the first save.
 */
export const BUTTON_SLOT_COUNT: ButtonCommandSlots["length"] = 16

const hasEverySlot = (
  slots: readonly ButtonCommandSlot[]
): slots is ButtonCommandSlots => slots.length === BUTTON_SLOT_COUNT

/**
 * The one place a slot list becomes a full slot set, so editing helpers can
 * work with plain arrays without an unchecked cast reaching the save request.
 */
export const toButtonCommandSlots = (
  slots: readonly ButtonCommandSlot[]
): ButtonCommandSlots => {
  if (!hasEverySlot(slots)) {
    throw new RangeError(
      `a button profile needs exactly ${BUTTON_SLOT_COUNT} slots, received ${slots.length}`
    )
  }
  return slots
}

export type ButtonCommandType =
  NonNullable<ButtonCommand>["type"] | "unassigned"
