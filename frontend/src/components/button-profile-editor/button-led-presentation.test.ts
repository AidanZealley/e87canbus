import { describe, expect, it } from "vitest"

import type { SteeringState } from "@/api/live-contract.gen"
import { deriveButtonProfileLedPreview } from "./button-led-presentation"

const steering = {
  mode: "auto",
  maximum_assistance_active: false,
} as SteeringState

describe("draft LED presentation", () => {
  it("derives colors from draft command positions rather than an active program", () => {
    const result = deriveButtonProfileLedPreview(
      [
        null,
        { type: "select_steering_mode", mode: "manual" },
        { type: "start_high_beam_strobe" },
      ],
      { synchronized: true, steering, servotronicUsable: true }
    )

    expect(result).toEqual([
      [0, 0, 0],
      [0, 0, 255],
      [8, 8, 8],
    ])
  })

  it("uses the unavailable presentation when live state cannot inform preview", () => {
    expect(
      deriveButtonProfileLedPreview(
        [{ type: "toggle_automatic_assistance" }, null],
        { synchronized: false, steering: null, servotronicUsable: false }
      )
    ).toEqual([
      [8, 6, 0],
      [0, 0, 0],
    ])
  })

  it("allows the presentation strategy to be replaced", () => {
    expect(
      deriveButtonProfileLedPreview(
        [{ type: "start_high_beam_strobe" }],
        { synchronized: true, steering, servotronicUsable: true },
        () => [1, 2, 3]
      )
    ).toEqual([[1, 2, 3]])
  })
})
