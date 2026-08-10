import { describe, expect, it } from "vitest"

import type { SteeringState } from "@e87canbus/coordinator-client/api/live-contract.gen"
import type { ButtonCommand, ButtonCommandSlot } from "./types"
import {
  BUTTON_LED_RGB,
  deriveButtonProfileLedPreview,
} from "./button-led-presentation"

describe("backend colour constants", () => {
  // Pinned against hosts/src/e87canbus/domain/events.py (RGB_*) and
  // domain/controller/button_leds.py (SOFT_*). Changing a colour there must
  // break this test rather than silently leave the editor preview wrong.
  it("matches the values named in the coordinator LED modules", () => {
    expect(BUTTON_LED_RGB).toEqual({
      RGB_OFF: [0, 0, 0],
      SOFT_AMBER: [8, 6, 0],
    })
  })
})

const steering = {
  mode: "auto",
  manual_assistance_level: 3,
  maximum_assistance_active: false,
} as SteeringState

const slot = (
  command: NonNullable<ButtonCommand>,
  colour: [number, number, number] = [100, 150, 200]
): NonNullable<ButtonCommandSlot> => ({
  command,
  colour,
  active_colour: null,
  animation: null,
})

const context = {
  synchronized: true,
  steering,
  servotronicUsable: true,
} as const

describe("button profile LED presentation", () => {
  it("renders unassigned slots as off and inactive authored colours as dim", () => {
    expect(
      deriveButtonProfileLedPreview(
        [
          null,
          slot({ type: "select_steering_mode", mode: "manual" }),
          slot({ type: "start_high_beam_strobe" }),
        ],
        context
      )
    ).toEqual([
      [0, 0, 0],
      [3, 5, 6],
      [3, 5, 6],
    ])
  })

  it("rounds the pinned white and amber resting colours to nearest integer", () => {
    expect(
      deriveButtonProfileLedPreview(
        [
          slot({ type: "start_high_beam_strobe" }, [255, 255, 255]),
          slot({ type: "start_high_beam_strobe" }, [255, 191, 0]),
        ],
        context
      )
    ).toEqual([
      [8, 8, 8],
      [8, 6, 0],
    ])
  })

  it("mirrors every parameter-dependent active predicate", () => {
    expect(
      deriveButtonProfileLedPreview(
        [
          slot({ type: "select_steering_mode", mode: "auto" }),
          slot({ type: "toggle_automatic_assistance" }),
          slot({ type: "set_manual_assistance_level", level: 3 }),
          slot({ type: "set_maximum_assistance", enabled: false }),
          slot({ type: "toggle_maximum_assistance" }),
          slot({ type: "adjust_manual_assistance", delta: 1 }),
          slot({ type: "start_high_beam_strobe" }),
        ],
        context
      )
    ).toEqual([
      [100, 150, 200],
      [100, 150, 200],
      [3, 5, 6],
      [100, 150, 200],
      [3, 5, 6],
      [3, 5, 6],
      [3, 5, 6],
    ])
  })

  it("activates only the selected manual assistance level in manual mode", () => {
    const manual = {
      ...steering,
      mode: "manual",
    } as SteeringState

    expect(
      deriveButtonProfileLedPreview(
        [
          slot({ type: "set_manual_assistance_level", level: 3 }),
          slot({ type: "set_manual_assistance_level", level: 2 }),
        ],
        { ...context, steering: manual }
      )
    ).toEqual([
      [100, 150, 200],
      [3, 5, 6],
    ])
  })

  it("treats maximum assistance as manual for mode and level predicates", () => {
    const maximum = {
      ...steering,
      mode: "auto",
      maximum_assistance_active: true,
    } as SteeringState

    expect(
      deriveButtonProfileLedPreview(
        [
          slot({ type: "select_steering_mode", mode: "manual" }),
          slot({ type: "set_manual_assistance_level", level: 3 }),
          slot({ type: "set_maximum_assistance", enabled: true }),
          slot({ type: "toggle_maximum_assistance" }),
        ],
        { ...context, steering: maximum }
      )
    ).toEqual([
      [100, 150, 200],
      [3, 5, 6],
      [100, 150, 200],
      [100, 150, 200],
    ])
  })

  it("uses full brightness without animating the active preview", () => {
    const animated = {
      ...slot({ type: "toggle_automatic_assistance" }, [9, 8, 7]),
      animation: { kind: "blink", on_ms: 400, off_ms: 400 },
    } satisfies NonNullable<ButtonCommandSlot>

    expect(deriveButtonProfileLedPreview([animated], context)).toEqual([
      [9, 8, 7],
    ])
  })

  it("uses unavailable before active when the link or capability is unusable", () => {
    expect(
      deriveButtonProfileLedPreview(
        [
          slot({ type: "toggle_automatic_assistance" }),
          slot({ type: "start_high_beam_strobe" }),
        ],
        { ...context, servotronicUsable: false }
      )
    ).toEqual([
      [8, 6, 0],
      [3, 5, 6],
    ])

    expect(
      deriveButtonProfileLedPreview(
        [slot({ type: "start_high_beam_strobe" }), null],
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
        [slot({ type: "start_high_beam_strobe" })],
        context,
        () => [1, 2, 3]
      )
    ).toEqual([[1, 2, 3]])
  })
})
