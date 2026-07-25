import {
  toButtonCommandSlots,
  type ButtonCommand,
  type ButtonCommandSlots,
} from "./types"

export type ButtonProfileDraft = {
  sourceRevision: number
  baseSlots: ButtonCommandSlots
  slots: ButtonCommandSlots
}

/** A draft that matches the saved profile exactly, so it reads as not dirty. */
export const pristineButtonProfileDraft = (
  revision: number,
  slots: readonly ButtonCommand[]
): ButtonProfileDraft => {
  const snapshot = toButtonCommandSlots([...slots])
  return { sourceRevision: revision, baseSlots: snapshot, slots: snapshot }
}

/**
 * Exhaustive over the command union so an eighth command type is a type error
 * rather than a slot that silently compares equal to whatever it replaced.
 */
const isSameCommand = (left: ButtonCommand, right: ButtonCommand): boolean => {
  if (left === null || right === null) return left === right
  switch (left.type) {
    case "select_steering_mode":
      return right.type === "select_steering_mode" && right.mode === left.mode
    case "adjust_manual_assistance":
      return (
        right.type === "adjust_manual_assistance" && right.delta === left.delta
      )
    case "set_manual_assistance_level":
      return (
        right.type === "set_manual_assistance_level" &&
        right.level === left.level
      )
    case "set_maximum_assistance":
      return (
        right.type === "set_maximum_assistance" &&
        right.enabled === left.enabled
      )
    case "toggle_automatic_assistance":
    case "toggle_maximum_assistance":
    case "start_high_beam_strobe":
      return right.type === left.type
  }
}

export const isButtonProfileDraftDirty = (
  draft: ButtonProfileDraft | null
): boolean =>
  draft !== null &&
  draft.slots.some(
    (command, index) => !isSameCommand(command, draft.baseSlots[index])
  )

/**
 * The draft the editor shows for a given saved profile.
 *
 * Only unsaved edits pin an earlier revision; a pristine editor follows the
 * query result, so neither a refetch nor a re-render can discard unsaved work
 * and no state has to be written back from an effect.
 */
export const resolveButtonProfileDraft = (
  pendingEdit: ButtonProfileDraft | null,
  revision: number,
  slots: readonly ButtonCommand[]
): ButtonProfileDraft =>
  pendingEdit !== null && isButtonProfileDraftDirty(pendingEdit)
    ? pendingEdit
    : pristineButtonProfileDraft(revision, slots)

export const buttonProfileStatusLabel = ({
  synchronized,
  sameProfile,
  sameRevision,
}: {
  synchronized: boolean
  sameProfile: boolean
  sameRevision: boolean
}): string => {
  if (!synchronized) return "Status unavailable"
  if (sameProfile && sameRevision) return "Active"
  if (sameProfile) return "Saved changes not active"
  return "Inactive"
}
