import { describe, expect, it } from "vitest"

import {
  commandHasActiveState,
  commandLabel,
  commandWithField,
  defaultCommandForType,
  defaultColourForCommand,
} from "./utils"

describe("button profile commands", () => {
  it("builds commands and applies generated field values", () => {
    expect(defaultCommandForType("select_steering_mode")).toEqual({
      type: "select_steering_mode",
      mode: "auto",
    })
    expect(defaultCommandForType("set_manual_assistance_level")).toEqual({
      type: "set_manual_assistance_level",
      level: 0,
    })
    expect(
      commandWithField(
        { type: "set_maximum_assistance", enabled: true },
        "enabled",
        false
      )
    ).toEqual({ type: "set_maximum_assistance", enabled: false })
    expect(defaultCommandForType("start_high_beam_strobe")).toEqual({
      type: "start_high_beam_strobe",
    })
  })

  it("reads active-state support from the generated catalogue", () => {
    expect(commandHasActiveState({ type: "toggle_automatic_assistance" })).toBe(
      true
    )
    expect(commandHasActiveState({ type: "start_high_beam_strobe" })).toBe(
      false
    )
  })

  it("produces concise item labels", () => {
    expect(commandLabel(null)).toBe("Unassigned")
    expect(
      commandLabel({ type: "set_manual_assistance_level", level: 4 })
    ).toBe("Assist 4")
    expect(commandLabel({ type: "adjust_manual_assistance", delta: 1 })).toBe(
      "Assist +"
    )
  })

  it("seeds the coordinator defaults for newly assigned commands", () => {
    expect(
      defaultColourForCommand({
        type: "select_steering_mode",
        mode: "manual",
      })
    ).toEqual([0, 0, 255])
    expect(
      defaultColourForCommand({ type: "toggle_automatic_assistance" })
    ).toEqual([0, 0, 255])
    expect(
      defaultColourForCommand({
        type: "set_manual_assistance_level",
        level: 4,
      })
    ).toEqual([255, 255, 255])
  })
})
