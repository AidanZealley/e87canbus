import { describe, expect, it } from "vitest"

import { colourHasVisibleRestingState, hexToRgb, rgbToHex } from "./colour"

describe("button profile colours", () => {
  it("round-trips exact RGB hex values", () => {
    expect(rgbToHex([0, 102, 255])).toBe("#0066FF")
    expect(hexToRgb("#0066ff")).toEqual([0, 102, 255])
    expect(hexToRgb("0066FF")).toEqual([0, 102, 255])
    expect(hexToRgb("#xyz")).toBeNull()
  })

  it("rejects colours whose rounded resting state is off", () => {
    expect(colourHasVisibleRestingState([15, 15, 15])).toBe(false)
    expect(colourHasVisibleRestingState([16, 0, 0])).toBe(true)
  })
})
