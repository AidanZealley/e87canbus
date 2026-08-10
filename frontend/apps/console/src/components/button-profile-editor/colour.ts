import {
  restingButtonLedRgb,
  type ButtonLedRgb,
} from "./button-led-presentation"

export type ButtonColour = [number, number, number]

export const rgbToHex = (rgb: ButtonLedRgb): string =>
  `#${rgb.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`.toUpperCase()

export const hexToRgb = (value: string): ButtonColour | null => {
  const match = /^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(value.trim())
  if (match === null) return null
  return [
    Number.parseInt(match[1], 16),
    Number.parseInt(match[2], 16),
    Number.parseInt(match[3], 16),
  ]
}

export const colourHasVisibleRestingState = (rgb: ButtonLedRgb): boolean =>
  restingButtonLedRgb(rgb).some((channel) => channel > 0)

export const rgbCss = (rgb: ButtonLedRgb): string => `rgb(${rgb.join(" ")})`
