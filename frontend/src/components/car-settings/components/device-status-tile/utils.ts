import type { DeviceRegistryEntryState } from "@/api/live-contract.gen"

export type DeviceStatusTone = "positive" | "caution" | "negative" | "neutral"

export type DeviceStatusPresentation = {
  tone: DeviceStatusTone
  label: string
  detail: string
}

export const deviceStatusPresentation = (
  device: DeviceRegistryEntryState
): DeviceStatusPresentation => {
  switch (device.status) {
    case "active":
      return { tone: "positive", label: "Active", detail: "Reporting normally" }
    case "pending":
      return {
        tone: "caution",
        label: "Pending",
        detail: "Waiting for heartbeat",
      }
    case "stale":
      return { tone: "caution", label: "Stale", detail: "Contact lost" }
    case "incompatible":
      return {
        tone: "negative",
        label: "Incompatible",
        detail: "Unsupported protocol",
      }
    case "fault":
      return {
        tone: "negative",
        label: "Fault",
        detail:
          device.last_status_code === null
            ? "Reported a fault"
            : `Reported status code ${device.last_status_code}`,
      }
    case "disabled":
      return { tone: "neutral", label: "Disabled", detail: "Not in use" }
    case "not_found":
      return {
        tone: "neutral",
        label: "Not found",
        detail: "Never seen on the bus",
      }
  }
}
