// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
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

vi.mock("@/components/ui/slider", () => ({
  Slider: ({
    "aria-label": ariaLabel,
    onValueCommitted,
  }: {
    "aria-label": string
    onValueCommitted?: (value: number[]) => void
  }) => (
    <button type="button" onClick={() => onValueCommitted?.([1])}>
      Commit {ariaLabel}
    </button>
  ),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const engine = {
  rpm: { value: null, status: "never_observed" as const },
  oil_temperature_c: { value: null, status: "never_observed" as const },
  coolant_temperature_c: { value: null, status: "never_observed" as const },
}

const renderControls = (speedKph: number | null = null) =>
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { mutations: { retry: false } },
        })
      }
    >
      <SimulatedVehicleControls speedKph={speedKph} engine={engine} />
    </QueryClientProvider>
  )

it("starts a realistic warm, idling car", async () => {
  renderControls()

  fireEvent.click(screen.getByRole("button", { name: "Start car" }))

  await waitFor(() => {
    expect(api.setVehicleSpeed).toHaveBeenCalledWith(0)
    expect(api.setEngineRpm).toHaveBeenCalledWith(600)
    expect(api.setOilTemperature).toHaveBeenCalledWith(90)
    expect(api.setCoolantTemperature).toHaveBeenCalledWith(90)
  })
})

it("stops every simulated vehicle signal together", async () => {
  renderControls(0)

  fireEvent.click(screen.getByRole("button", { name: "Stop car" }))

  await waitFor(() => {
    expect(api.silenceVehicleSpeed).toHaveBeenCalledOnce()
    expect(api.silenceEngineRpm).toHaveBeenCalledOnce()
    expect(api.silenceOilTemperature).toHaveBeenCalledOnce()
    expect(api.silenceCoolantTemperature).toHaveBeenCalledOnce()
  })
})

it("commits a slider value without a separate set action", async () => {
  renderControls(0)

  fireEvent.click(
    screen.getByRole("button", { name: "Commit Simulated vehicle speed" })
  )

  await waitFor(() => expect(api.setVehicleSpeed.mock.calls[0]?.[0]).toBe(1))
})
