// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { afterEach, expect, it, vi } from "vitest"

import { tapButton } from "@/api/simulator"
import { useLiveStore } from "@/live/live-store"
import { snapshot } from "@/live/test-fixtures"
import { SimulatorNeoTrellis } from "./SimulatorNeoTrellis"

vi.mock("@/api/simulator", () => ({ tapButton: vi.fn() }))

const renderWithQueryClient = (ui: ReactNode) =>
  render(
    <QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>
  )

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  useLiveStore.getState().reset()
})

it("clears retained LED observations and disables controls when unsynchronized", () => {
  const value = snapshot("dev-boot", 4)
  value.data.buttons.led_colours[0] = 3
  value.data.devices.networks = [
    {
      id: "kcan",
      label: "K-CAN",
      interface: "can0",
      bitrate: 100_000,
      connected: true,
      nodes: ["Pi", "NeoTrellis"],
    },
  ]
  useLiveStore.getState().applySnapshot(value)
  renderWithQueryClient(<SimulatorNeoTrellis />)

  const firstButton = screen.getByRole("button", { name: "Button 0" })
  expect(firstButton.style.getPropertyValue("--button-led-rgb")).toBe("0 0 255")
  expect((firstButton as HTMLButtonElement).disabled).toBe(true)

  act(() => useLiveStore.getState().transportDisconnected())

  expect(firstButton.style.getPropertyValue("--button-led-rgb")).toBe("0 0 0")
})

it("sends emulator taps when the emulated source is selected", async () => {
  const value = snapshot("dev-boot", 5)
  value.data.buttons.led_colours = [2, ...Array(15).fill(0)]
  value.data.devices.registry.button_pad = {
    ...value.data.devices.registry.button_pad,
    source_mode: "emulated",
    status: "active",
    protocol_version: 1,
    device_session_id: 2,
  }
  useLiveStore.getState().applySnapshot(value)
  renderWithQueryClient(<SimulatorNeoTrellis />)

  const firstButton = screen.getByRole("button", { name: "Button 0" })
  expect(firstButton.style.getPropertyValue("--button-led-rgb")).toBe("0 255 0")
  fireEvent.click(firstButton)
  await waitFor(() => expect(tapButton).toHaveBeenCalledWith(0))
})

it("disables wire controls for a physical button-pad source", async () => {
  const value = snapshot("physical-boot", 6)
  value.data.devices.registry.button_pad = {
    ...value.data.devices.registry.button_pad,
    source_mode: "physical",
    status: "active",
    protocol_version: 1,
    device_session_id: 3,
  }
  useLiveStore.getState().applySnapshot(value)
  renderWithQueryClient(<SimulatorNeoTrellis />)

  const wireButton = screen.getByRole("button", { name: "Button 0" })
  expect((wireButton as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(wireButton)
  expect(tapButton).not.toHaveBeenCalled()
})
