import type { ButtonProfileDefinitionRequest } from "@/api/http"

export type ButtonCommand = ButtonProfileDefinitionRequest["slots"][number]
export type ButtonCommandType =
  NonNullable<ButtonCommand>["type"] | "unassigned"

export type ButtonCommandDraft = {
  type: ButtonCommandType
  mode: "auto" | "manual"
  delta: "-1" | "1"
  level: string
  enabled: "true" | "false"
}
