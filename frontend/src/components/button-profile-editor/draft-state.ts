import type { ButtonCommand } from "./types"

export type ButtonProfileDraft = {
  sourceRevision: number
  baseSlots: ButtonCommand[]
  slots: ButtonCommand[]
}

export const isButtonProfileDraftDirty = (
  draft: ButtonProfileDraft | null
): boolean =>
  draft !== null &&
  JSON.stringify(draft.slots) !== JSON.stringify(draft.baseSlots)

export const synchronizeButtonProfileDraft = (
  draft: ButtonProfileDraft | null,
  revision: number,
  slots: readonly ButtonCommand[]
): { draft: ButtonProfileDraft; serverChanged: boolean } => {
  if (
    draft !== null &&
    draft.sourceRevision !== revision &&
    isButtonProfileDraftDirty(draft)
  ) {
    return { draft, serverChanged: true }
  }
  if (draft !== null && draft.sourceRevision === revision) {
    return { draft, serverChanged: false }
  }
  const nextSlots = [...slots]
  return {
    draft: {
      sourceRevision: revision,
      baseSlots: nextSlots,
      slots: nextSlots,
    },
    serverChanged: false,
  }
}

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
