import type { DeviceRegistryEntry } from "@/api/live-events"
import {
  connectSimulatedDevice,
  disconnectSimulatedDevice,
  rebootSimulatedDevice,
  setSimulatedDeviceProtocolVersion,
  setSimulatedDeviceStatusCode,
} from "@/api/simulator"
import type {
  SimulatedDeviceAction,
  SimulatedDeviceActionAvailability,
} from "./SimulatedDeviceCard"

export const runSimulatedDeviceAction = (
  role: DeviceRegistryEntry["role"],
  action: SimulatedDeviceAction
) => {
  switch (action) {
    case "connect":
      return connectSimulatedDevice(role)
    case "disconnect":
      return disconnectSimulatedDevice(role)
    case "reboot":
      return rebootSimulatedDevice(role)
    case "incompatible":
      return setSimulatedDeviceProtocolVersion(role, 2)
    case "restore-compatible":
      return setSimulatedDeviceProtocolVersion(role, 1)
    case "fault":
      return setSimulatedDeviceStatusCode(role, 1)
    case "clear-fault":
      return setSimulatedDeviceStatusCode(role, 0)
  }
}

export const simulatedDeviceActions = (
  entry: DeviceRegistryEntry,
  synchronized: boolean
): SimulatedDeviceActionAvailability => {
  const controllable = synchronized && entry.source_mode === "emulated"
  return {
    connect:
      controllable &&
      (entry.status === "not_found" || entry.status === "stale"),
    disconnect:
      controllable &&
      entry.status !== "disabled" &&
      entry.status !== "not_found",
    reboot:
      controllable &&
      entry.status !== "disabled" &&
      entry.status !== "not_found",
    incompatible:
      controllable &&
      entry.status !== "incompatible" &&
      entry.status !== "not_found",
    "restore-compatible": controllable && entry.status === "incompatible",
    fault: controllable && entry.status === "active",
    "clear-fault": controllable && entry.status === "fault",
  }
}
