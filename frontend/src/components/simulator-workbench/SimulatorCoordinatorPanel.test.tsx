// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, expect, it, vi } from "vitest"

import type { SimulationCoordinatorPanelState } from "@/api/http/types.gen"
import { SimulatorCoordinatorPanel } from "./SimulatorCoordinatorPanel"

const api = vi.hoisted(() => ({
  getSimulationCoordinatorPanel: vi.fn(),
  pressSimulationCoordinatorPanelButton: vi.fn(),
  connectSimulationHotspotClient: vi.fn(),
  disconnectSimulationHotspotClient: vi.fn(),
  failNextSimulationHotspotOperation: vi.fn(),
  previewSimulationCoordinatorStatus: vi.fn(),
}))

vi.mock("@/api/http/sdk.gen", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/http/sdk.gen")>()),
  ...api,
}))

const state = (
  overrides: Partial<SimulationCoordinatorPanelState> = {}
): SimulationCoordinatorPanelState => ({
  coordinator_status: "ready",
  coordinator_status_preview: null,
  display: "ready",
  failure_armed: false,
  hotspot_status: "disabled",
  ...overrides,
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

it("renders shared state and sends controls to the simulator backend", async () => {
  api.getSimulationCoordinatorPanel.mockResolvedValue(state())
  api.pressSimulationCoordinatorPanelButton.mockResolvedValue(
    state({ display: "hotspot_waiting", hotspot_status: "starting" })
  )
  api.connectSimulationHotspotClient.mockResolvedValue(
    state({ display: "hotspot_connected", hotspot_status: "connected" })
  )
  api.previewSimulationCoordinatorStatus.mockResolvedValue(
    state({
      coordinator_status: "fault",
      coordinator_status_preview: "fault",
      display: "fault",
    })
  )
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <SimulatorCoordinatorPanel />
    </QueryClientProvider>
  )

  expect(
    await screen.findByRole("img", { name: "Coordinator indicator: Ready" })
  ).toBeTruthy()

  fireEvent.click(
    screen.getByRole("button", { name: "Press coordinator hotspot button" })
  )
  await waitFor(() =>
    expect(api.pressSimulationCoordinatorPanelButton).toHaveBeenCalledOnce()
  )
  expect(
    screen.getByRole("img", {
      name: "Coordinator indicator: Hotspot waiting for a client",
    })
  ).toBeTruthy()

  fireEvent.click(screen.getByRole("button", { name: "Connect client" }))
  await waitFor(() =>
    expect(api.connectSimulationHotspotClient).toHaveBeenCalledOnce()
  )
  expect(
    screen.getByRole("img", {
      name: "Coordinator indicator: Hotspot client connected",
    })
  ).toBeTruthy()

  fireEvent.click(
    screen.getByRole("combobox", { name: "Coordinator condition" })
  )
  const fault = screen.getByRole("option", { name: "Fault" })
  fireEvent.pointerDown(fault, { pointerType: "mouse" })
  fireEvent.click(fault)
  await waitFor(() =>
    expect(api.previewSimulationCoordinatorStatus).toHaveBeenCalledWith({
      body: { status: "fault" },
      throwOnError: true,
    })
  )
  expect(
    screen.getByRole("img", { name: "Coordinator indicator: Fault" })
  ).toBeTruthy()

  queryClient.clear()
})
