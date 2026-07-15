// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

import { useLiveStore } from "@/live/live-store"
import { snapshot } from "@/live/test-fixtures"
import { NetworkTopology } from "./components/network-topology/NetworkTopology"
import { SteeringStatus } from "./components/steering-status/SteeringStatus"
import { SimulatorNeoTrellis } from "./SimulatorNeoTrellis"

afterEach(() => {
  cleanup()
  useLiveStore.getState().reset()
})

it("removes retained /dev steering, topology, and LED observations when unsynchronized", () => {
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
  render(
    <>
      <SimulatorNeoTrellis
        pressedButtons={new Set()}
        maximumAssistanceActive={false}
        semanticCommandPending={false}
        onMaximumAssistanceChange={() => {}}
        onPress={() => {}}
        onRelease={() => {}}
      />
      <SteeringStatus />
      <NetworkTopology />
    </>
  )

  const firstButton = screen.getByRole("button", { name: "Button 0, idle" })
  expect(firstButton.style.boxShadow).toContain("0 0 255")
  expect((firstButton as HTMLButtonElement).disabled).toBe(true)
  expect(screen.getByText("Steering assist")).toBeTruthy()
  expect(screen.getByText("K-CAN")).toBeTruthy()

  act(() => useLiveStore.getState().transportDisconnected())

  expect(firstButton.style.boxShadow).toContain("0 0 0")
  expect(screen.queryByText("Steering assist")).toBeNull()
  expect(screen.queryByText("K-CAN")).toBeNull()
  expect(
    (screen.getByRole("button", { name: "Enable maximum" }) as HTMLButtonElement)
      .disabled
  ).toBe(true)
})

it("labels semantic controller control separately from emulator wire exercise", () => {
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
  const onPress = vi.fn()
  const onMaximumAssistanceChange = vi.fn()

  render(
    <SimulatorNeoTrellis
      pressedButtons={new Set()}
      maximumAssistanceActive={false}
      semanticCommandPending={false}
      onMaximumAssistanceChange={onMaximumAssistanceChange}
      onPress={onPress}
      onRelease={() => {}}
    />
  )

  expect(screen.getByText("Source: emulated")).toBeTruthy()
  expect(screen.getByText(/decoded by the emulator/)).toBeTruthy()
  const firstButton = screen.getByRole("button", { name: "Button 0, idle" })
  expect(firstButton.style.boxShadow).toContain("0 255 0")
  fireEvent.pointerDown(firstButton)
  expect(onPress).toHaveBeenCalledWith(0)
  expect(onMaximumAssistanceChange).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole("button", { name: "Enable maximum" }))
  expect(onMaximumAssistanceChange).toHaveBeenCalledWith(true)
  expect(onPress).toHaveBeenCalledTimes(1)
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
  const onPress = vi.fn()
  const onMaximumAssistanceChange = vi.fn()

  render(
    <SimulatorNeoTrellis
      pressedButtons={new Set()}
      maximumAssistanceActive={false}
      semanticCommandPending={false}
      onMaximumAssistanceChange={onMaximumAssistanceChange}
      onPress={onPress}
      onRelease={() => {}}
    />
  )

  expect(screen.getByText("Source: observer")).toBeTruthy()
  expect(screen.getByText(/Observed LEDs unknown/)).toBeTruthy()
  expect(screen.getByText(/available only for the emulated role/)).toBeTruthy()
  const wireButton = screen.getByRole("button", { name: "Button 0, idle" })
  expect((wireButton as HTMLButtonElement).disabled).toBe(true)
  fireEvent.pointerDown(wireButton)
  expect(onPress).not.toHaveBeenCalled()

  const semanticButton = screen.getByRole("button", { name: "Enable maximum" })
  expect((semanticButton as HTMLButtonElement).disabled).toBe(false)
  fireEvent.click(semanticButton)
  expect(onMaximumAssistanceChange).toHaveBeenCalledWith(true)
})
