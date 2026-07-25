import { describe, expect, it } from "vitest"

import {
  commandLabel,
  commandToFormValue,
  formValueToCommand,
} from "./utils"

describe("button profile command conversion", () => {
  it("round-trips every parameterized command", () => {
    const commands = [
      { type: "select_steering_mode", mode: "manual" },
      { type: "adjust_manual_assistance", delta: -1 },
      { type: "set_manual_assistance_level", level: 6 },
      { type: "set_maximum_assistance", enabled: false },
    ] as const

    expect(
      commands.map((command) =>
        formValueToCommand(commandToFormValue(command))
      )
    ).toEqual(commands)
  })

  it("converts unassigned and parameterless commands", () => {
    expect(formValueToCommand(commandToFormValue(null))).toBeNull()
    expect(
      formValueToCommand(
        commandToFormValue({ type: "start_high_beam_strobe" })
      )
    ).toEqual({ type: "start_high_beam_strobe" })
  })

  it("produces concise grid labels", () => {
    expect(commandLabel(null)).toBe("Unassigned")
    expect(
      commandLabel({ type: "set_manual_assistance_level", level: 4 })
    ).toBe("Assist 4")
    expect(commandLabel({ type: "adjust_manual_assistance", delta: 1 })).toBe(
      "Assist +"
    )
  })
})
