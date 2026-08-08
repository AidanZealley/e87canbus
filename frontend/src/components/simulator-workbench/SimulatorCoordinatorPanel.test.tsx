// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, it } from "vitest"

import { SimulatorCoordinatorPanel } from "./SimulatorCoordinatorPanel"

afterEach(cleanup)

it("previews the panel with local mock state", () => {
  render(<SimulatorCoordinatorPanel />)

  expect(
    screen.getByRole("img", { name: "Coordinator indicator: Ready" })
  ).toBeTruthy()

  fireEvent.click(
    screen.getByRole("button", { name: "Press coordinator hotspot button" })
  )

  expect(
    screen.getByRole("img", {
      name: "Coordinator indicator: Hotspot waiting for a client",
    })
  ).toBeTruthy()
})
