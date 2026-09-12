// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, expect, it, vi } from "vitest"

import type { SimulationCoordinatorPanelState } from "@e87canbus/coordinator-client/api/http/types.gen"
import { SimulatorCoordinatorPanel } from "./SimulatorCoordinatorPanel"

const api = vi.hoisted(() => ({
  getSimulationCoordinatorPanel: vi.fn(),
  previewSimulationCoordinatorStatus: vi.fn(),
}))

vi.mock("@e87canbus/coordinator-client/api/http/sdk.gen", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@e87canbus/coordinator-client/api/http/sdk.gen")>()),
  ...api,
}))

const state = (
  overrides: Partial<SimulationCoordinatorPanelState> = {}
): SimulationCoordinatorPanelState => ({
  coordinator_status: "ready",
  coordinator_status_preview: null,
  ...overrides,
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

it("renders coordinator state and previews panel conditions", async () => {
  api.getSimulationCoordinatorPanel.mockResolvedValue(state())
  api.previewSimulationCoordinatorStatus.mockResolvedValue(
    state({
      coordinator_status: "fault",
      coordinator_status_preview: "fault",
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
