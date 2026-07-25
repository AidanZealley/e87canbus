import { describe, expect, it } from "vitest"

import type { SteeringState } from "@/api/live-contract.gen"
import {
  BUTTON_LED_RGB,
  deriveButtonProfileLedPreview,
} from "./button-led-presentation"

describe("backend colour constants", () => {
  // Pinned against coordinator/src/e87canbus/domain/events.py (RGB_*) and
  // domain/controller/button_leds.py (SOFT_*). Changing a colour there must
  // break this test rather than silently leave the draft preview wrong.
  it("matches the values named in the coordinator LED modules", () => {
    expect(BUTTON_LED_RGB).toEqual({
      RGB_OFF: [0, 0, 0],
      RGB_BLUE: [0, 0, 255],
      RGB_AMBER: [255, 191, 0],
      RGB_WHITE: [255, 255, 255],
      SOFT_WHITE: [8, 8, 8],
      SOFT_AMBER: [8, 6, 0],
    })
  })
})

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
