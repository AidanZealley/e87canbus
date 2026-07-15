import type { DevicesState } from "@/api/live-events"

export const LED_COUNT = 16

export const formatSteeringReason = (
  reason: NonNullable<DevicesState["steering_controller"]>["last_command_reason"]
) => (reason === null ? "No command accepted" : reason.replaceAll("_", " "))
