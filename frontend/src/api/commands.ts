import { requestApi } from "./client.ts"

export type CommandAcknowledgement = {
  accepted: true
  boot_id: string
  revision: number
}

export const setMaximumAssistance = (enabled: boolean) =>
  requestApi<CommandAcknowledgement>(
    "/api/commands/maximum-assistance",
    "Controller command",
    {
      method: "PUT",
      body: JSON.stringify({ enabled }),
    }
  )

export const setSteeringMode = (
  mode: "auto" | "manual",
  manualLevel?: number
) =>
  requestApi<CommandAcknowledgement>(
    "/api/commands/steering-mode",
    "Controller command",
    {
      method: "PUT",
      body: JSON.stringify({
        mode,
        manual_level: manualLevel ?? null,
      }),
    }
  )
