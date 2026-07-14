// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

import { SimulatedVehicleControls } from "./SimulatedVehicleControls"

afterEach(cleanup)

it("submits a bounded vehicle speed and can stop the speed signal", () => {
  const onSetSpeed = vi.fn()
  const onSilenceSpeed = vi.fn()

  render(
    <SimulatedVehicleControls
      speedKph={10}
      onSetSpeed={onSetSpeed}
      onSilenceSpeed={onSilenceSpeed}
    />
  )

  const speedInput = screen.getByRole("spinbutton", { name: "Vehicle speed" })
  fireEvent.change(speedInput, { target: { value: "42.5" } })
  fireEvent.submit(speedInput.closest("form")!)
  expect(onSetSpeed).toHaveBeenCalledWith(42.5)

  fireEvent.click(screen.getByRole("button", { name: "Stop signal" }))
  expect(onSilenceSpeed).toHaveBeenCalledOnce()
})

it("disables signal controls while a simulator command is pending", () => {
  render(
    <SimulatedVehicleControls
      speedKph={null}
      disabled
      onSetSpeed={vi.fn()}
      onSilenceSpeed={vi.fn()}
    />
  )

  expect(
    (screen.getByRole("button", { name: "Set speed" }) as HTMLButtonElement)
      .disabled
  ).toBe(true)
  expect(
    (screen.getByRole("slider", {
      name: "Simulated vehicle speed",
    }) as HTMLInputElement).disabled
  ).toBe(true)
  expect(screen.getByText("No fresh speed signal")).toBeTruthy()
})
