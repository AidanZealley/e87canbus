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
  value.data.devices = {
    devices: [],
    networks: [
      {
        id: "kcan",
        label: "K-CAN",
        interface: "can0",
        bitrate: 100_000,
        connected: true,
        nodes: ["Pi", "NeoTrellis"],
      },
    ],
    steering_controller: {
      effective_assistance: 0.62,
      last_command_reason: "auto",
      watchdog_timed_out: false,
    },
  }
  useLiveStore.getState().applySnapshot(value)
  renderWithQueryClient(
    <SimulatorNeoTrellis
      maximumAssistanceActive={false}
      semanticCommandPending={false}
      onMaximumAssistanceChange={() => {}}
    />
  )

  const firstButton = screen.getByRole("button", { name: "Button 0" })
  expect(firstButton.style.boxShadow).toContain("0 0 255")
  expect((firstButton as HTMLButtonElement).disabled).toBe(true)

  act(() => useLiveStore.getState().transportDisconnected())

  expect(firstButton.style.boxShadow).toContain("0 0 0")
  expect(
    (
      screen.getByRole("button", {
        name: "Enable maximum",
      }) as HTMLButtonElement
    ).disabled
  ).toBe(true)
})

it("sends emulator taps separately from semantic controller commands", async () => {
  const value = snapshot("dev-boot", 5)
  value.data.devices.devices = [
    {
      id: "button_pad",
      label: "Button pad",
      source_mode: "emulated",
      connected: true,
      last_seen_monotonic_s: 2,
      desired_led_colours: Array(16).fill(0),
      observed_led_colours: [2, ...Array(15).fill(0)],
      last_output_fault: null,
    },
  ]
  useLiveStore.getState().applySnapshot(value)
  const onMaximumAssistanceChange = vi.fn()

  renderWithQueryClient(
    <SimulatorNeoTrellis
      maximumAssistanceActive={false}
      semanticCommandPending={false}
      onMaximumAssistanceChange={onMaximumAssistanceChange}
    />
  )

  const firstButton = screen.getByRole("button", { name: "Button 0" })
  expect(firstButton.style.boxShadow).toContain("0 255 0")
  fireEvent.click(firstButton)
  await waitFor(() => expect(tapButton).toHaveBeenCalledWith(0))
  expect(onMaximumAssistanceChange).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole("button", { name: "Enable maximum" }))
  expect(onMaximumAssistanceChange).toHaveBeenCalledWith(true)
  expect(tapButton).toHaveBeenCalledTimes(1)
})

it("keeps semantic control available while observer wire controls stay unavailable", () => {
  const value = snapshot("observer-boot", 6)
  value.data.devices.devices = [
    {
      id: "button_pad",
      label: "Button pad",
      source_mode: "observer",
      connected: null,
      last_seen_monotonic_s: null,
      desired_led_colours: [4, ...Array(15).fill(0)],
      observed_led_colours: null,
      last_output_fault: null,
    },
  ]
  useLiveStore.getState().applySnapshot(value)
  const onMaximumAssistanceChange = vi.fn()

  renderWithQueryClient(
    <SimulatorNeoTrellis
      maximumAssistanceActive={false}
      semanticCommandPending={false}
      onMaximumAssistanceChange={onMaximumAssistanceChange}
    />
  )

  const wireButton = screen.getByRole("button", { name: "Button 0" })
  expect((wireButton as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(wireButton)
  expect(tapButton).not.toHaveBeenCalled()

  const semanticButton = screen.getByRole("button", { name: "Enable maximum" })
  expect((semanticButton as HTMLButtonElement).disabled).toBe(false)
  fireEvent.click(semanticButton)
  expect(onMaximumAssistanceChange).toHaveBeenCalledWith(true)
})
