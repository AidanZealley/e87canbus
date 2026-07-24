import { describe, expect, it } from "vitest"

import {
  buttonProfileStatusLabel,
  synchronizeButtonProfileDraft,
  type ButtonProfileDraft,
} from "./draft-state"
import type { ButtonCommand } from "./types"

const blankSlots: ButtonCommand[] = Array.from({ length: 16 }, () => null)

describe("button profile draft synchronization", () => {
  it("adopts a newer server revision when the local draft is pristine", () => {
    const current: ButtonProfileDraft = {
      sourceRevision: 1,
      baseSlots: blankSlots,
      slots: blankSlots,
    }
    const newer = [...blankSlots]
    newer[0] = { type: "start_high_beam_strobe" }

    const result = synchronizeButtonProfileDraft(current, 2, newer)

    expect(result.serverChanged).toBe(false)
    expect(result.draft.sourceRevision).toBe(2)
    expect(result.draft.slots[0]).toEqual({ type: "start_high_beam_strobe" })
  })

  it("preserves dirty local edits and surfaces a server change", () => {
    const edited = [...blankSlots]
    edited[1] = { type: "toggle_maximum_assistance" }
    const current: ButtonProfileDraft = {
      sourceRevision: 1,
      baseSlots: blankSlots,
      slots: edited,
    }

    const result = synchronizeButtonProfileDraft(current, 2, blankSlots)

    expect(result).toEqual({ draft: current, serverChanged: true })
  })
})

it("never reports a profile active while live state is unsynchronized", () => {
  expect(
    buttonProfileStatusLabel({
      synchronized: false,
      sameProfile: true,
      sameRevision: true,
    })
  ).toBe("Status unavailable")
  expect(
    buttonProfileStatusLabel({
      synchronized: true,
      sameProfile: true,
      sameRevision: true,
    })
  ).toBe("Active")
})
