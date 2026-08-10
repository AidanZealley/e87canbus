import type { SteeringState } from "@e87canbus/coordinator-client/api/live-contract.gen"
import { isApiProblemResponse } from "@e87canbus/coordinator-client/api/is-api-problem"
import { toast } from "sonner"

export const LED_COUNT = 16

export const formatSteeringReason = (
  reason: NonNullable<SteeringState["servotronic"]>["last_command_reason"]
) => (reason === null ? "No command accepted" : reason.replaceAll("_", " "))

export const notifySimulatorError = (error: unknown) =>
  toast.error("Simulator action failed", {
    description: `${
      isApiProblemResponse(error)
        ? error.error.message
        : error instanceof Error
          ? error.message
          : "Simulator command failed."
    } Check that the backend is running on port 8000.`,
  })
