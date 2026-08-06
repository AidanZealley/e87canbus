// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

import type { EffectiveDisplay } from "@/api/live-contract.gen"
import { CoordinatorPanel } from "./CoordinatorPanel"

afterEach(cleanup)

it.each([
  ["starting", "Starting", "animate-panel-travel"],
  ["ready", "Ready", null],
  ["hotspot_waiting", "Hotspot waiting for a client", "animate-panel-pulse"],
  ["hotspot_connected", "Hotspot client connected", null],
  ["fault", "Fault", null],
  ["off", "Off", null],
] as const)("renders the %s semantic display", (display, label, animation) => {
  const { container } = render(
    <CoordinatorPanel
      display={display satisfies EffectiveDisplay}
      onHotspotPress={() => undefined}
    />
  )

  expect(
    screen.getByRole("img", { name: `Coordinator indicator: ${label}` })
  ).toBeTruthy()
  const pixels = container.querySelectorAll("[data-panel-light]")
  expect(pixels).toHaveLength(5)
  if (animation !== null) {
    expect(pixels[0]?.className).toContain(animation)
  }
})

it("exposes the hotspot button without relying on colour", () => {
  const onHotspotPress = vi.fn()
  render(<CoordinatorPanel display="fault" onHotspotPress={onHotspotPress} />)

  expect(screen.getByText("Hotspot")).toBeTruthy()
  fireEvent.click(
    screen.getByRole("button", { name: "Press coordinator hotspot button" })
  )
  expect(onHotspotPress).toHaveBeenCalledOnce()
})
