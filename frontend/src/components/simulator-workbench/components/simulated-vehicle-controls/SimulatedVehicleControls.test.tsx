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

it("allows the vehicle speed input to be cleared before entering a new value", () => {
  const onSetSpeed = vi.fn()

  render(
    <SimulatedVehicleControls
      speedKph={0}
      onSetSpeed={onSetSpeed}
      onSilenceSpeed={vi.fn()}
    />
  )

  const speedInput = screen.getByRole("spinbutton", { name: "Vehicle speed" })
  const setSpeedButton = screen.getByRole("button", { name: "Set speed" })

  fireEvent.change(speedInput, { target: { value: "" } })
  expect((speedInput as HTMLInputElement).value).toBe("")
  expect((setSpeedButton as HTMLButtonElement).disabled).toBe(true)

  fireEvent.change(speedInput, { target: { value: "1" } })
  expect((speedInput as HTMLInputElement).value).toBe("1")
  fireEvent.click(setSpeedButton)
  expect(onSetSpeed).toHaveBeenCalledWith(1)
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
    screen
      .getByRole("group", { name: "Simulated vehicle speed" })
      .hasAttribute("data-disabled")
  ).toBe(true)
  expect(screen.getByText("No fresh speed signal")).toBeTruthy()
})
