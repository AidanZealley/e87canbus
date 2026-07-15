import type { DevicesState } from "@/api/live-events"
import { toast } from "sonner"

export const LED_COUNT = 16

export const formatSteeringReason = (
  reason: NonNullable<
    DevicesState["steering_controller"]
  >["last_command_reason"]
) => (reason === null ? "No command accepted" : reason.replaceAll("_", " "))

export const notifySimulatorError = (error: Error) =>
  toast.error("Simulator action failed", {
    description: `${error.message || "Simulator command failed."} Check that the backend is running on port 8000.`,
  })
