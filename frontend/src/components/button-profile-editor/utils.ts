import type {
  ButtonCommand,
  ButtonCommandFormValue,
  ButtonCommandType,
} from "./types"

export const commandTypeOptions: ReadonlyArray<{
  value: ButtonCommandType
  label: string
}> = [
  { value: "unassigned", label: "Unassigned" },
  { value: "select_steering_mode", label: "Select steering mode" },
  {
    value: "toggle_automatic_assistance",
    label: "Toggle automatic assistance",
  },
  { value: "adjust_manual_assistance", label: "Adjust manual assistance" },
  {
    value: "set_manual_assistance_level",
    label: "Set manual assistance level",
  },
  { value: "set_maximum_assistance", label: "Set maximum assistance" },
  {
    value: "toggle_maximum_assistance",
    label: "Toggle maximum assistance",
  },
  { value: "start_high_beam_strobe", label: "Start high-beam strobe" },
]

export const commandLabel = (command: ButtonCommand): string => {
  if (command === null) return "Unassigned"
  switch (command.type) {
    case "select_steering_mode":
      return `${command.mode === "auto" ? "Auto" : "Manual"} mode`
    case "toggle_automatic_assistance":
      return "Toggle auto"
    case "adjust_manual_assistance":
      return command.delta === 1 ? "Assist +" : "Assist −"
    case "set_manual_assistance_level":
      return `Assist ${command.level}`
    case "set_maximum_assistance":
      return command.enabled ? "Maximum on" : "Maximum off"
    case "toggle_maximum_assistance":
      return "Toggle maximum"
    case "start_high_beam_strobe":
      return "High-beam strobe"
  }
}

export const commandToFormValue = (
  command: ButtonCommand
): ButtonCommandFormValue => ({
  type: command?.type ?? "unassigned",
  mode: command?.type === "select_steering_mode" ? command.mode : "auto",
  delta:
    command?.type === "adjust_manual_assistance"
      ? command.delta === 1
        ? "1"
        : "-1"
      : "1",
  level:
    command?.type === "set_manual_assistance_level"
      ? String(command.level)
      : "0",
  enabled:
    command?.type === "set_maximum_assistance"
      ? command.enabled
        ? "true"
        : "false"
      : "true",
})

export const formValueToCommand = (
  value: ButtonCommandFormValue
): ButtonCommand => {
  switch (value.type) {
    case "unassigned":
      return null
    case "select_steering_mode":
      return { type: value.type, mode: value.mode }
    case "toggle_automatic_assistance":
    case "toggle_maximum_assistance":
    case "start_high_beam_strobe":
      return { type: value.type }
    case "adjust_manual_assistance":
      return { type: value.type, delta: Number(value.delta) as -1 | 1 }
    case "set_manual_assistance_level":
      return { type: value.type, level: Number(value.level) }
    case "set_maximum_assistance":
      return { type: value.type, enabled: value.enabled === "true" }
  }
}
