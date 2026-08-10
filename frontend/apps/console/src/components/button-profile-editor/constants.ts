import type { ButtonLedRgb } from "./button-led-presentation"

export const BUTTON_ANIMATION_SPEED_PRESETS = [
  {
    value: "slow",
    label: "Slow",
    breathePeriodMs: 4000,
    blinkOnMs: 800,
    blinkOffMs: 800,
  },
  {
    value: "medium",
    label: "Medium",
    breathePeriodMs: 2000,
    blinkOnMs: 400,
    blinkOffMs: 400,
  },
  {
    value: "fast",
    label: "Fast",
    breathePeriodMs: 1000,
    blinkOnMs: 200,
    blinkOffMs: 200,
  },
] as const

export type ButtonAnimationSpeed =
  (typeof BUTTON_ANIMATION_SPEED_PRESETS)[number]["value"]

export const DEFAULT_BUTTON_ANIMATION_SPEED: ButtonAnimationSpeed = "medium"

export const BUTTON_COLOUR_PRESETS: ReadonlyArray<{
  name: string
  colour: ButtonLedRgb
}> = [
  { name: "White", colour: [255, 255, 255] },
  { name: "Amber", colour: [255, 191, 0] },
  { name: "Yellow", colour: [255, 255, 0] },
  { name: "Orange", colour: [255, 96, 0] },
  { name: "Red", colour: [255, 0, 0] },
  { name: "Magenta", colour: [255, 0, 255] },
  { name: "Purple", colour: [128, 0, 255] },
  { name: "Blue", colour: [0, 0, 255] },
  { name: "Cyan", colour: [0, 255, 255] },
  { name: "Green", colour: [0, 255, 0] },
]
