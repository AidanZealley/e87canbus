// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, expect, it, vi } from "vitest"

import { useLiveStore } from "@/live/live-store"
import { snapshot } from "@/live/test-fixtures"
import { SimulatorWorkbench } from "./SimulatorWorkbench"

vi.mock("./components/simulated-vehicle-controls", () => ({
  SimulatedVehicleControls: ({
    speedKph,
    engine,
    devices,
  }: {
    speedKph: number | null
    engine: { rpm: { value: number | null; status: string } }
    devices: unknown[]
  }) => (
    <div data-testid="vehicle-controls">
      speed={speedKph ?? "unavailable"};rpm={engine.rpm.value ?? "unavailable"};
      status={engine.rpm.status};devices={devices.length}
    </div>
  ),
}))
vi.mock("./components/steering-curve-card", () => ({
  SteeringCurveCard: () => <div>Live steering curve</div>,
}))
vi.mock("./components/simulator-toolbar", () => ({
  SimulatorToolbar: () => <div>Toolbar</div>,
}))
vi.mock("./components/network-topology", () => ({
  NetworkTopology: () => null,
}))
vi.mock("./components/steering-status", () => ({
  SteeringStatus: () => null,
}))
vi.mock("./SimulatorNeoTrellis", () => ({ SimulatorNeoTrellis: () => null }))
vi.mock("./SimulatorTrace", () => ({ SimulatorTrace: () => null }))

afterEach(() => {
  cleanup()
  useLiveStore.getState().reset()
})

it("masks workbench vehicle controls and curve state while disconnected", () => {
  const value = snapshot("workbench-boot", 5)
  value.data.vehicle = { speed_kph: 72, speed_valid: true }
  value.data.engine.rpm = { value: 4100, status: "valid" }
  value.data.devices.devices = [
    {
      id: "button_pad",
      label: "Button pad",
      status: "online",
      reason: null,
    },
  ]
  value.data.devices.steering_controller = {
    effective_assistance: 0.5,
    last_command_reason: "auto",
    watchdog_timed_out: false,
  }
  useLiveStore.getState().applySnapshot(value)
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SimulatorWorkbench />
    </QueryClientProvider>
  )
  expect(
    screen.getByTestId("vehicle-controls").textContent?.replaceAll(" ", "")
  ).toContain("speed=72;rpm=4100;status=valid;devices=1")
  expect(screen.getByText("Live steering curve")).toBeTruthy()

  act(() => useLiveStore.getState().transportDisconnected())

  expect(
    screen.getByTestId("vehicle-controls").textContent?.replaceAll(" ", "")
  ).toContain("speed=unavailable;rpm=unavailable;status=stale;devices=0")
  expect(screen.queryByText("Live steering curve")).toBeNull()
})
