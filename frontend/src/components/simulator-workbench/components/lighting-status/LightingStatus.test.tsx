// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, expect, it } from "vitest"

import { snapshot } from "@/live/test-fixtures"
import { useLiveStore } from "@/live/live-store"
import { LightingStatus } from "./LightingStatus"

afterEach(() => {
  cleanup()
  useLiveStore.getState().reset()
})

it("shows separate requested and observed high-beam state with completed-cycle progress", () => {
  const value = snapshot("lighting", 4)
  value.data.lighting = {
    high_beam_enabled: true,
    high_beam_strobe_active: true,
    high_beam_strobe_cycles_remaining: 3,
    observed_high_beam_enabled: false,
  }
  useLiveStore.getState().applySnapshot(value)

  render(<LightingStatus />)

  expect(screen.getByText("Requested")).toBeTruthy()
  expect(screen.getAllByText("High beam on")).toHaveLength(1)
  expect(screen.getAllByText("High beam off")).toHaveLength(1)
  expect(screen.getByText("2 / 5 cycles complete")).toBeTruthy()
  expect(screen.getByText("3 cycles remaining")).toBeTruthy()
  expect(
    screen
      .getByRole("progressbar", { name: "2 / 5 cycles complete" })
      .getAttribute("aria-valuenow")
  ).toBe("40")
})

it("shows zero completed cycles while the strobe is idle", () => {
  const value = snapshot("lighting", 4)
  useLiveStore.getState().applySnapshot(value)

  render(<LightingStatus />)

  expect(screen.getByText("0 / 5 cycles complete")).toBeTruthy()
  expect(screen.getByText("Strobe idle")).toBeTruthy()
})

it("does not render until live state has synchronized", () => {
  render(<LightingStatus />)
  expect(screen.queryByText("High-beam strobe")).toBeNull()
})
