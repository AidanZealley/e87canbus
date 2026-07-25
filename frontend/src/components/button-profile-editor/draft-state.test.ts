import { describe, expect, it } from "vitest"

import {
  buttonProfileStatusLabel,
  isButtonProfileDraftDirty,
  pristineButtonProfileDraft,
  resolveButtonProfileDraft,
} from "./draft-state"
import { toButtonCommandSlots, type ButtonCommand } from "./types"

const blankSlots = toButtonCommandSlots(
  Array.from({ length: 16 }, () => null as ButtonCommand)
)
const withSlot = (index: number, command: ButtonCommand) => {
  const slots = [...blankSlots]
  slots[index] = command
  return toButtonCommandSlots(slots)
}

describe("button profile draft resolution", () => {
  it("adopts a newer server revision when there is no pending edit", () => {
    const newer = withSlot(0, { type: "start_high_beam_strobe" })

    const draft = resolveButtonProfileDraft(
      pristineButtonProfileDraft(1, blankSlots),
      2,
      newer
    )

    expect(draft.sourceRevision).toBe(2)
    expect(draft.slots[0]).toEqual({ type: "start_high_beam_strobe" })
    expect(isButtonProfileDraftDirty(draft)).toBe(false)
  })

  it("adopts the server revision when nothing has been edited yet", () => {
    const draft = resolveButtonProfileDraft(null, 3, blankSlots)

    expect(draft.sourceRevision).toBe(3)
    expect(isButtonProfileDraftDirty(draft)).toBe(false)
  })

  it("preserves dirty local edits against a newer server revision", () => {
    const pendingEdit = {
      ...pristineButtonProfileDraft(1, blankSlots),
      slots: withSlot(1, { type: "toggle_maximum_assistance" }),
    }

    const draft = resolveButtonProfileDraft(pendingEdit, 2, blankSlots)

    expect(draft).toBe(pendingEdit)
    // The stale source revision is what surfaces the "Saved profile changed" alert.
    expect(draft.sourceRevision).toBe(1)
  })

  it("falls back to the saved profile once an edit is undone", () => {
    const pendingEdit = pristineButtonProfileDraft(1, blankSlots)

    const draft = resolveButtonProfileDraft(pendingEdit, 2, blankSlots)

    expect(draft.sourceRevision).toBe(2)
  })
})

describe("button profile draft dirtiness", () => {
  it("compares slots structurally rather than by key order", () => {
    const base = pristineButtonProfileDraft(
      1,
      withSlot(0, { type: "select_steering_mode", mode: "auto" })
    )

    expect(isButtonProfileDraftDirty(base)).toBe(false)
    expect(
      isButtonProfileDraftDirty({
        ...base,
        slots: withSlot(0, {
          mode: "auto",
          type: "select_steering_mode",
        } as ButtonCommand),
      })
    ).toBe(false)
    expect(
      isButtonProfileDraftDirty({
        ...base,
        slots: withSlot(0, { type: "select_steering_mode", mode: "manual" }),
      })
    ).toBe(true)
  })

  it("detects assignment and clearing of a slot", () => {
    const base = pristineButtonProfileDraft(1, blankSlots)

    expect(
      isButtonProfileDraftDirty({
        ...base,
        slots: withSlot(4, { type: "set_manual_assistance_level", level: 3 }),
      })
    ).toBe(true)
    expect(
      isButtonProfileDraftDirty({
        ...base,
        baseSlots: withSlot(4, {
          type: "set_manual_assistance_level",
          level: 3,
        }),
      })
    ).toBe(true)
  })
})

it("rejects a command list that is not a full slot set", () => {
  expect(() => toButtonCommandSlots([null, null])).toThrow(RangeError)
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
