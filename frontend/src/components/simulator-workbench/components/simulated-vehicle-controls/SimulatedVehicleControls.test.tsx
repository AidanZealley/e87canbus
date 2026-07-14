// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

import { SimulatedVehicleControls } from "./SimulatedVehicleControls"

afterEach(cleanup)

const engine = {
  rpm: { value: null, status: "never_observed" as const },
  oil_temperature_c: { value: 112.5, status: "valid" as const },
  coolant_temperature_c: { value: null, status: "stale" as const },
}

const callbacks = () => ({
  onSetRpm: vi.fn(),
  onSilenceRpm: vi.fn(),
  onSetOilTemperature: vi.fn(),
  onSilenceOilTemperature: vi.fn(),
  onSetCoolantTemperature: vi.fn(),
  onSilenceCoolantTemperature: vi.fn(),
})

it("submits a bounded vehicle speed and can stop the speed signal", () => {
  const onSetSpeed = vi.fn()
  const onSilenceSpeed = vi.fn()

  render(
    <SimulatedVehicleControls
      speedKph={10}
      engine={engine}
      onSetSpeed={onSetSpeed}
      onSilenceSpeed={onSilenceSpeed}
      {...callbacks()}
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
      engine={engine}
      onSetSpeed={onSetSpeed}
      onSilenceSpeed={vi.fn()}
      {...callbacks()}
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
      engine={engine}
      disabled
      onSetSpeed={vi.fn()}
      onSilenceSpeed={vi.fn()}
      {...callbacks()}
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
  expect(
    (screen.getByRole("spinbutton", { name: "Engine RPM" }) as HTMLInputElement)
      .disabled
  ).toBe(true)
})

it("sets and silences each engine signal while showing independent statuses", () => {
  const actions = callbacks()
  const { container } = render(
    <SimulatedVehicleControls
      speedKph={0}
      engine={engine}
      onSetSpeed={vi.fn()}
      onSilenceSpeed={vi.fn()}
      {...actions}
    />
  )

  const rpm = screen.getByRole("spinbutton", { name: "Engine RPM" })
  fireEvent.change(rpm, { target: { value: "4200" } })
  fireEvent.submit(rpm.closest("form")!)
  expect(actions.onSetRpm).toHaveBeenCalledWith(4200)

  const oil = screen.getByRole("spinbutton", { name: "Oil temperature" })
  fireEvent.change(oil, { target: { value: "110" } })
  fireEvent.submit(oil.closest("form")!)
  expect(actions.onSetOilTemperature).toHaveBeenCalledWith(110)
  const oilSilence = oil
    .closest("form")!
    .querySelector<HTMLButtonElement>('button[type="button"]')
  fireEvent.click(oilSilence!)
  expect(actions.onSilenceOilTemperature).toHaveBeenCalledOnce()

  const coolant = screen.getByRole("spinbutton", {
    name: "Coolant temperature",
  })
  fireEvent.change(coolant, { target: { value: "95" } })
  fireEvent.submit(coolant.closest("form")!)
  expect(actions.onSetCoolantTemperature).toHaveBeenCalledWith(95)

  expect(screen.getByText("Never observed")).toBeTruthy()
  expect(screen.getByText("Valid · 112.5")).toBeTruthy()
  expect(screen.getByText("Stale")).toBeTruthy()
  expect(container.textContent).toContain("none are BMW definitions")
})

it("calls the matching silence action for every valid engine signal", () => {
  const actions = callbacks()
  render(
    <SimulatedVehicleControls
      speedKph={0}
      engine={{
        rpm: { value: 3500, status: "valid" },
        oil_temperature_c: { value: 112.5, status: "valid" },
        coolant_temperature_c: { value: 98, status: "valid" },
      }}
      onSetSpeed={vi.fn()}
      onSilenceSpeed={vi.fn()}
      {...actions}
    />
  )

  for (const label of [
    "Engine RPM",
    "Oil temperature",
    "Coolant temperature",
  ]) {
    const input = screen.getByRole("spinbutton", { name: label })
    const silence = input
      .closest("form")!
      .querySelector<HTMLButtonElement>('button[type="button"]')
    fireEvent.click(silence!)
  }

  expect(actions.onSilenceRpm).toHaveBeenCalledOnce()
  expect(actions.onSilenceOilTemperature).toHaveBeenCalledOnce()
  expect(actions.onSilenceCoolantTemperature).toHaveBeenCalledOnce()
})
