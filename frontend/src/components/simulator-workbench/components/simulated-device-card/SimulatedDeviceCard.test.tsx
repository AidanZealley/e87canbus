// @vitest-environment jsdom
import { render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

import type { DeviceRegistryEntry } from "@/api/live-events"
import {
  SimulatedDeviceCard,
  simulatedDeviceActions,
  type SimulatedDeviceAction,
} from "./index"

const entry = (status: DeviceRegistryEntry["status"]): DeviceRegistryEntry => ({
  role: "button_pad",
  label: "Button pad",
  device_id: 1,
  source_mode: "emulated",
  status,
  protocol_version: status === "not_found" ? null : 1,
  device_session_id: status === "not_found" ? null : 4,
  last_status_code: status === "fault" ? 7 : null,
  last_transition_monotonic_s: status === "not_found" ? null : 2,
})

const allActions = (): Record<SimulatedDeviceAction, boolean> => ({
  connect: true,
  disconnect: true,
  reboot: true,
  incompatible: true,
  "restore-compatible": true,
  fault: true,
  "clear-fault": true,
})

afterEach(() => vi.restoreAllMocks())

it("renders server status, diagnostics, children, and contextual pending/error state", () => {
  const callbacks = Object.fromEntries(
    (Object.keys(allActions()) as SimulatedDeviceAction[]).map((action) => [
      action,
      vi.fn(),
    ])
  )

  render(
    <SimulatedDeviceCard
      role="button_pad"
      registryEntry={entry("pending")}
      availableActions={allActions()}
      callbacks={callbacks}
      pendingAction="disconnect"
      errorMessage="simulation command failed"
    >
      <div data-testid="peer-child">peer panel</div>
    </SimulatedDeviceCard>
  )

  expect(screen.getByLabelText("Status: pending").textContent).toBe("Pending")
  expect(
    screen.getByText("peer panel").closest("[data-device-role=button_pad]")
  ).toBeTruthy()
  expect(screen.queryByText("Device status code")).toBeNull()
  expect(screen.getByRole("alert").textContent).toBe("simulation command failed")
  expect((screen.getByRole("button", { name: "Disconnect…" }) as HTMLButtonElement).disabled).toBe(true)
  expect((screen.getByRole("button", { name: "Connect" }) as HTMLButtonElement).disabled).toBe(true)
})

it("derives context actions from the authoritative registry entry", () => {
  const active = simulatedDeviceActions(entry("active"), true)
  expect(active).toMatchObject({
    connect: false,
    disconnect: true,
    reboot: true,
    incompatible: true,
    "restore-compatible": false,
    fault: true,
    "clear-fault": false,
  })

  const notFound = simulatedDeviceActions(entry("not_found"), true)
  expect(notFound.connect).toBe(true)
  expect(notFound.disconnect).toBe(false)
  expect(simulatedDeviceActions(entry("active"), false).disconnect).toBe(false)
})
