// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, expect, it, vi } from "vitest"

import { useLiveStore } from "@/live/live-store"
import { snapshot } from "@/live/test-fixtures"
import { SimulatorWorkbench } from "./SimulatorWorkbench"

vi.mock(
  "./components/simulated-vehicle-controls/SimulatedVehicleControls",
  () => ({
    SimulatedVehicleControls: ({
      speedKph,
      engine,
    }: {
      speedKph: number | null
      engine: { rpm: { value: number | null; status: string } }
    }) => (
      <div data-testid="vehicle-controls">
        speed={speedKph ?? "unavailable"};rpm=
        {engine.rpm.value ?? "unavailable"}; status={engine.rpm.status}
      </div>
    ),
  })
)
vi.mock("./components/steering-curve-card", () => ({
  SteeringCurveCard: ({
    activationAvailable,
    modeControlAvailable,
  }: {
    activationAvailable: boolean
    modeControlAvailable: boolean
  }) => (
    <div data-testid="curve-configuration">
      {activationAvailable ? "enabled" : "disabled"};controls=
      {modeControlAvailable ? "enabled" : "disabled"}
    </div>
  ),
}))
vi.mock("./components/simulator-toolbar", () => ({
  SimulatorToolbar: () => <div>Toolbar</div>,
}))
vi.mock("./components/network-topology/NetworkTopology", () => ({
  NetworkTopology: () => null,
}))
vi.mock("./components/steering-status/SteeringStatus", () => ({
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
  value.data.devices.registry.button_pad = {
    ...value.data.devices.registry.button_pad,
    source_mode: "emulated",
    status: "active",
    protocol_version: 1,
    device_session_id: 1,
  }
  value.data.steering.servotronic = {
    effective_assistance: 0.5,
    last_command_reason: "auto",
    watchdog_timed_out: false,
    active_curve_source: null,
    active_curve_revision: null,
    active_curve_crc32: null,
    observed_speed_kph: null,
    speed_fresh: null,
    pwm_duty: null,
    inhibit_reason: null,
  }
  useLiveStore.getState().applySnapshot(value)
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SimulatorWorkbench />
    </QueryClientProvider>
  )
  expect(
    screen.getByTestId("vehicle-controls").textContent?.replaceAll(" ", "")
  ).toContain("speed=72;rpm=4100;status=valid")
  expect(screen.getByTestId("curve-configuration")).toBeTruthy()

  act(() => useLiveStore.getState().transportDisconnected())

  expect(
    screen.getByTestId("vehicle-controls").textContent?.replaceAll(" ", "")
  ).toContain("speed=unavailable;rpm=unavailable;status=stale")
  expect(screen.queryByTestId("curve-configuration")).toBeNull()
})

it.each([
  ["bench active", "active", true, "enabled"],
  ["bench absent", "not_found", true, "disabled"],
  ["active without config TX", "active", false, "disabled"],
] as const)(
  "gates curve activation for %s",
  (_label, status, capability, expected) => {
    const value = snapshot("capability-boot", 6)
    value.data.devices.registry.servotronic_controller = {
      ...value.data.devices.registry.servotronic_controller,
      source_mode: "physical",
      status,
    }
    value.data.steering.curve_configuration_available = capability
    useLiveStore.getState().applySnapshot(value)
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SimulatorWorkbench />
      </QueryClientProvider>
    )
    expect(screen.getByTestId("curve-configuration").textContent).toContain(
      expected
    )
    expect(screen.getByTestId("curve-configuration").textContent).toContain(
      `controls=${status === "active" ? "enabled" : "disabled"}`
    )
  }
)
