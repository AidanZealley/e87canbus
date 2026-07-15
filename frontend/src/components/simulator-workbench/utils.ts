import type { DevicesState } from "@/api/live-events"

export const LED_COUNT = 16

type Device = DevicesState["devices"][number]
export type PresentedDevice = Omit<Device, "reason"> & {
  reason: string | null
}

export const formatSteeringReason = (
  reason: NonNullable<DevicesState["steering_controller"]>["last_command_reason"]
) => (reason === null ? "No command accepted" : reason.replaceAll("_", " "))

export const deviceOrUnavailable = (
  devices: readonly PresentedDevice[],
  id: Device["id"],
  label: string
): PresentedDevice =>
  devices.find((device) => device.id === id) ?? {
    id,
    label,
    status: "offline",
    reason: "unavailable",
  }
