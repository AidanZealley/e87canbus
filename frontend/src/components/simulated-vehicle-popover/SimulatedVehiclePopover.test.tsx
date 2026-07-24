// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, expect, it, vi } from "vitest"

import { useLiveStore } from "@/live/live-store"
import { snapshot } from "@/live/test-fixtures"
import { SimulatedVehiclePopover } from "./SimulatedVehiclePopover"

const runtime = vi.hoisted(() => ({
  simulatedVehicle: false,
}))

vi.mock("@/api/http/@tanstack/react-query.gen", () => ({
  getRuntimeConfigurationOptions: () => ({
    queryKey: ["runtime-configuration"],
    queryFn: async () => ({
      profile: runtime.simulatedVehicle ? "simulator" : "car",
      capabilities: {
        simulated_vehicle: runtime.simulatedVehicle,
        simulation_workbench: runtime.simulatedVehicle,
      },
    }),
  }),
}))

vi.mock(
  "@/components/simulator-workbench/LiveSimulatedVehicleControls",
  () => ({
    LiveSimulatedVehicleControls: () => <div>Vehicle control content</div>,
  })
)

const renderPopover = () =>
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false } },
        })
      }
    >
      <SimulatedVehiclePopover />
    </QueryClientProvider>
  )

afterEach(() => {
  cleanup()
  runtime.simulatedVehicle = false
  useLiveStore.getState().reset()
})

it("stays hidden when simulated vehicle control is unavailable", async () => {
  renderPopover()

  await waitFor(() => {
    expect(
      screen.queryByRole("button", {
        name: "Open simulated vehicle controls",
      })
    ).toBeNull()
  })
})

it("renders a floating trigger when simulated vehicle control is available", async () => {
  runtime.simulatedVehicle = true
  renderPopover()

  expect(
    await screen.findByRole("button", {
      name: "Open simulated vehicle controls",
    })
  ).toBeTruthy()
  expect(
    screen.getByRole("button", { name: "Start simulated car" }).className
  ).toContain("bg-success/10")
})

it("makes the power shortcut destructive while the car is running", async () => {
  runtime.simulatedVehicle = true
  const live = snapshot("running-car", 1)
  live.data.vehicle = { speed_kph: 0, speed_valid: true }
  useLiveStore.getState().applySnapshot(live)
  renderPopover()

  expect(
    (await screen.findByRole("button", { name: "Stop simulated car" })).className
  ).toContain("bg-destructive/10")
})
