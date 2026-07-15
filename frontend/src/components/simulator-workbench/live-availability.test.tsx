// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react"
import { afterEach, expect, it } from "vitest"

import { useLiveStore } from "@/live/live-store"
import { snapshot } from "@/live/test-fixtures"
import { NetworkTopology } from "./components/network-topology"
import { SteeringStatus } from "./components/steering-status"
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
        onPress={() => {}}
        onRelease={() => {}}
      />
      <SteeringStatus />
      <NetworkTopology />
    </>
  )

  const firstButton = screen.getByRole("button", { name: "Button 0, idle" })
  expect(firstButton.style.boxShadow).toContain("0 0 255")
  expect(screen.getByText("Steering assist")).toBeTruthy()
  expect(screen.getByText("K-CAN")).toBeTruthy()

  act(() => useLiveStore.getState().transportDisconnected())

  expect(firstButton.style.boxShadow).toContain("0 0 0")
  expect(screen.queryByText("Steering assist")).toBeNull()
  expect(screen.queryByText("K-CAN")).toBeNull()
})
