// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

import {
  setSimulatedHotspotClient,
  setSimulatedHotspotFailure,
  setSimulatedPanelLink,
  tapCoordinatorPanelButton,
  triggerCoordinatorFailure,
} from "@/api/http/sdk.gen"
import { useLiveStore } from "@/live/live-store"
import { snapshot } from "@/live/test-fixtures"
import { SimulatorCoordinatorPanel } from "./SimulatorCoordinatorPanel"

vi.mock("@/api/http/sdk.gen", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/http/sdk.gen")>()),
  tapCoordinatorPanelButton: vi.fn(),
  setSimulatedHotspotClient: vi.fn(),
  setSimulatedHotspotFailure: vi.fn(),
  setSimulatedPanelLink: vi.fn(),
  triggerCoordinatorFailure: vi.fn(),
}))

const renderPanel = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SimulatorCoordinatorPanel />
    </QueryClientProvider>
  )

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  useLiveStore.getState().reset()
})

it("submits simulator causes without assigning semantic state", async () => {
  const value = snapshot("panel-boot", 3)
  value.data.local_controls!.state = {
    client_connected: true,
    desired_display: "hotspot_connected",
    diagnostic: null,
    effective_display: "hotspot_connected",
    hotspot: "active",
    panel_link: "connected",
  }
  useLiveStore.getState().applySnapshot(value)
  renderPanel()

  fireEvent.click(
    screen.getByRole("button", { name: "Press coordinator hotspot button" })
  )
  fireEvent.click(screen.getByRole("button", { name: "Disconnect laptop" }))
  fireEvent.click(screen.getByRole("button", { name: "Disconnect panel" }))
  fireEvent.click(screen.getByRole("button", { name: "Fail hotspot" }))
  fireEvent.click(screen.getByRole("button", { name: "Fail coordinator" }))

  await waitFor(() => {
    expect(tapCoordinatorPanelButton).toHaveBeenCalledWith({
      throwOnError: true,
    })
    expect(setSimulatedHotspotClient).toHaveBeenCalledWith({
      body: { connected: false },
      throwOnError: true,
    })
    expect(setSimulatedPanelLink).toHaveBeenCalledWith({
      body: { connected: false },
      throwOnError: true,
    })
    expect(setSimulatedHotspotFailure).toHaveBeenCalledWith({
      body: { enabled: true },
      throwOnError: true,
    })
    expect(triggerCoordinatorFailure).toHaveBeenCalledWith({
      throwOnError: true,
    })
  })
})

it("shows authoritative coordinator failure as reset-only", () => {
  const value = snapshot("panel-boot", 7)
  value.data.health.fatal = true
  value.data.local_controls!.state = {
    client_connected: false,
    desired_display: "fault",
    diagnostic: null,
    effective_display: "fault",
    hotspot: "disabled",
    panel_link: "connected",
  }
  useLiveStore.getState().applySnapshot(value)
  renderPanel()

  const failed = screen.getByRole("button", { name: "Coordinator failed" })
  expect((failed as HTMLButtonElement).disabled).toBe(true)
  expect(
    screen.getByRole("img", { name: "Coordinator indicator: Fault" })
  ).toBeTruthy()
})

it("shows effective link-loss behavior and recovery causes", async () => {
  const value = snapshot("panel-boot", 4)
  value.data.local_controls!.state = {
    client_connected: false,
    desired_display: "ready",
    diagnostic: "panel link disconnected",
    effective_display: "fault",
    hotspot: "fault",
    panel_link: "disconnected",
  }
  useLiveStore.getState().applySnapshot(value)
  renderPanel()

  expect(
    screen.getByRole("img", { name: "Coordinator indicator: Fault" })
  ).toBeTruthy()
  expect(screen.getByText("ready")).toBeTruthy()
  expect(screen.getByRole("status").textContent).toContain(
    "panel link disconnected"
  )

  fireEvent.click(screen.getByRole("button", { name: "Reconnect panel" }))
  fireEvent.click(screen.getByRole("button", { name: "Recover hotspot" }))
  await waitFor(() => {
    expect(setSimulatedPanelLink).toHaveBeenCalledWith({
      body: { connected: true },
      throwOnError: true,
    })
    expect(setSimulatedHotspotFailure).toHaveBeenCalledWith({
      body: { enabled: false },
      throwOnError: true,
    })
  })
})

it("does not expose controls before reconnect hydration", () => {
  renderPanel()
  expect(
    screen.queryByRole("heading", { name: "Coordinator panel" })
  ).toBeNull()
})

it("does not offer a client connection before hotspot activation completes", () => {
  const value = snapshot("panel-boot", 5)
  value.data.local_controls!.state = {
    client_connected: false,
    desired_display: "hotspot_waiting",
    diagnostic: null,
    effective_display: "hotspot_waiting",
    hotspot: "activating",
    panel_link: "connected",
  }
  useLiveStore.getState().applySnapshot(value)
  renderPanel()

  expect(
    (
      screen.getByRole("button", {
        name: "Connect laptop",
      }) as HTMLButtonElement
    ).disabled
  ).toBe(true)
})

it("does not describe a semantic fault as operational without a diagnostic", () => {
  const value = snapshot("panel-boot", 6)
  value.data.local_controls!.state = {
    client_connected: false,
    desired_display: "fault",
    diagnostic: null,
    effective_display: "fault",
    hotspot: "disabled",
    panel_link: "connected",
  }
  useLiveStore.getState().applySnapshot(value)
  renderPanel()

  expect(
    screen.getByRole("img", { name: "Coordinator indicator: Fault" })
  ).toBeTruthy()
  expect(screen.queryByText("Operational")).toBeNull()
})
