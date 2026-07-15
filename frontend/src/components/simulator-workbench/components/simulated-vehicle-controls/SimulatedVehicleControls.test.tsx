// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, expect, it, vi } from "vitest"

import { SimulatedVehicleControls } from "./SimulatedVehicleControls"

const api = vi.hoisted(() => ({
  setVehicleSpeed: vi.fn(),
  silenceVehicleSpeed: vi.fn(),
  setEngineRpm: vi.fn(),
  silenceEngineRpm: vi.fn(),
  setOilTemperature: vi.fn(),
  silenceOilTemperature: vi.fn(),
  setCoolantTemperature: vi.fn(),
  silenceCoolantTemperature: vi.fn(),
}))

vi.mock("@/api/simulator", () => api)

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const engine = {
  rpm: { value: null, status: "never_observed" as const },
  oil_temperature_c: { value: 112.5, status: "valid" as const },
  coolant_temperature_c: { value: null, status: "stale" as const },
}
const renderControls = (
  props: Partial<Parameters<typeof SimulatedVehicleControls>[0]> = {}
) =>
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      <SimulatedVehicleControls
        speedKph={10}
        engine={engine}
        {...props}
      />
    </QueryClientProvider>
  )

it("submits commands through mutations and preserves independent telemetry status", async () => {
  renderControls()
  const speed = screen.getByRole("spinbutton", { name: "Vehicle speed" })
  fireEvent.change(speed, { target: { value: "42.5" } })
  fireEvent.submit(speed.closest("form")!)
  await waitFor(() => expect(api.setVehicleSpeed).toHaveBeenCalledWith(42.5))
  fireEvent.click(screen.getByRole("button", { name: "Stop signal" }))
  await waitFor(() => expect(api.silenceVehicleSpeed).toHaveBeenCalledOnce())

  const rpm = screen.getByRole("spinbutton", { name: "Engine RPM" })
  fireEvent.change(rpm, { target: { value: "4200" } })
  fireEvent.submit(rpm.closest("form")!)
  await waitFor(() => expect(api.setEngineRpm).toHaveBeenCalledWith(4200))
  expect(screen.getByText("Never observed")).toBeTruthy()
  expect(screen.getByText("Valid · 112.5")).toBeTruthy()
  expect(screen.getByText("Stale")).toBeTruthy()
})

it("sends the exact set and silence action for every engine signal", async () => {
  renderControls({
    engine: {
      rpm: { value: 3000, status: "valid" },
      oil_temperature_c: { value: 90, status: "valid" },
      coolant_temperature_c: { value: 80, status: "valid" },
    },
  })

  const cases = [
    {
      label: "Engine RPM",
      value: "4200",
      set: api.setEngineRpm,
      silence: api.silenceEngineRpm,
    },
    {
      label: "Oil temperature",
      value: "111",
      set: api.setOilTemperature,
      silence: api.silenceOilTemperature,
    },
    {
      label: "Coolant temperature",
      value: "96",
      set: api.setCoolantTemperature,
      silence: api.silenceCoolantTemperature,
    },
  ]

  for (const signal of cases) {
    const input = screen.getByRole("spinbutton", { name: signal.label })
    const form = input.closest("form")!
    fireEvent.change(input, { target: { value: signal.value } })
    fireEvent.submit(form)
    await waitFor(() =>
      expect(signal.set).toHaveBeenCalledWith(Number(signal.value))
    )
    fireEvent.click(form.querySelectorAll("button")[1]!)
    await waitFor(() => expect(signal.silence).toHaveBeenCalledOnce())
  }
})

it("does not submit a locally cleared speed draft", () => {
  renderControls()
  const speed = screen.getByRole("spinbutton", { name: "Vehicle speed" })
  fireEvent.change(speed, { target: { value: "" } })
  expect(
    (screen.getByRole("button", { name: "Set speed" }) as HTMLButtonElement)
      .disabled
  ).toBe(true)
  fireEvent.submit(speed.closest("form")!)
  expect(api.setVehicleSpeed).not.toHaveBeenCalled()
})

it("limits pending presentation to the initiating control", async () => {
  let resolve!: () => void
  api.setVehicleSpeed.mockReturnValueOnce(
    new Promise<void>((done) => {
      resolve = done
    })
  )
  renderControls()
  fireEvent.click(screen.getByRole("button", { name: "Set speed" }))
  await waitFor(() =>
    expect(
      (screen.getByRole("button", { name: "Set speed" }) as HTMLButtonElement)
        .disabled
    ).toBe(true)
  )
  expect(
    (screen.getByRole("spinbutton", { name: "Engine RPM" }) as HTMLInputElement)
      .disabled
  ).toBe(false)
  resolve()
})
