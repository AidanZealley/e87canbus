import type { DeviceRegistryEntry } from "@/api/live-events"
import type {
  SimulatedDeviceActionAvailability,
} from "./SimulatedDeviceCard"

export const simulatedDeviceActions = (
  entry: DeviceRegistryEntry,
  synchronized: boolean
): SimulatedDeviceActionAvailability => {
  const controllable = synchronized && entry.source_mode === "emulated"
  return {
    connect:
      controllable && (entry.status === "not_found" || entry.status === "stale"),
    disconnect:
      controllable && entry.status !== "disabled" && entry.status !== "not_found",
    reboot:
      controllable && entry.status !== "disabled" && entry.status !== "not_found",
    incompatible:
      controllable && entry.status !== "incompatible" && entry.status !== "not_found",
    "restore-compatible": controllable && entry.status === "incompatible",
    fault: controllable && entry.status === "active",
    "clear-fault": controllable && entry.status === "fault",
  }
}
