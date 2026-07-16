import { expect, it } from "vitest"

import type { DeviceRegistryEntry } from "@/api/live-events"
import { simulatedDeviceActions, statusActionForControl } from "./index"

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

it("derives direct transitions between incompatible and fault states", () => {
  expect(statusActionForControl("incompatible", "fault")).toBe(
    "recover-and-fault"
  )
  expect(statusActionForControl("fault", "incompatible")).toBe(
    "recover-and-incompatible"
  )
})
