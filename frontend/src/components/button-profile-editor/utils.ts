import {
  BUTTON_COMMAND_CATALOGUE,
  type ButtonCommandSpec,
} from "@/api/button-command-catalogue.gen"
import { zButtonProfileSlotRequest } from "@/api/http/zod.gen"
import type { ButtonCommand, ButtonCommandType } from "./types"

export const defaultColourForCommand = (
  command: NonNullable<ButtonCommand>
): [number, number, number] =>
  command.type === "select_steering_mode" ||
  command.type === "toggle_automatic_assistance"
    ? [0, 0, 255]
    : [255, 255, 255]

export const sentenceLabel = (value: string | number | boolean): string => {
  const text = String(value).replaceAll("_", " ")
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}`
}

export const commandTypeOptions: ReadonlyArray<{
  value: ButtonCommandType
  label: string
}> = [
  { value: "unassigned", label: "Unassigned" },
  ...BUTTON_COMMAND_CATALOGUE.map(({ type }) => ({
    value: type,
    label: sentenceLabel(type),
  })),
]

export const buttonCommandSpec = (
  type: string
): ButtonCommandSpec | undefined =>
  BUTTON_COMMAND_CATALOGUE.find((spec) => spec.type === type)

export const commandHasActiveState = (
  command: NonNullable<ButtonCommand>
): boolean => buttonCommandSpec(command.type)?.hasActiveState ?? false

const commandSchema = zButtonProfileSlotRequest.shape.command

export const defaultCommandForType = (
  type: Exclude<ButtonCommandType, "unassigned">
): NonNullable<ButtonCommand> => {
  const spec = buttonCommandSpec(type)
  if (spec === undefined) {
    throw new RangeError(`unknown button command type: ${type}`)
  }
  const command = Object.fromEntries([
    ["type", type],
    ...spec.fields.map((field) => {
      switch (field.kind) {
        case "enum":
          return [field.name, field.values[0]]
        case "boolean":
          return [field.name, true]
        case "integer":
          return [field.name, field.minimum ?? 0]
      }
    }),
  ])
  return commandSchema.parse(command)
}

export const commandWithField = (
  command: NonNullable<ButtonCommand>,
  name: string,
  value: string | number | boolean
): NonNullable<ButtonCommand> =>
  commandSchema.parse({ ...command, [name]: value })

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
