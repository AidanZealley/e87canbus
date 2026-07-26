import { BUTTON_COMMAND_CATALOGUE } from "@/api/button-command-catalogue.gen"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { ButtonCommand, ButtonCommandType } from "../../types"
import {
  buttonCommandSpec,
  commandTypeOptions,
  commandWithField,
  defaultCommandForType,
  sentenceLabel,
} from "../../utils"
import { ManualAssistanceSlider } from "../manual-assistance-slider"

type ButtonCommandEditorProps = {
  buttonIndex: number
  command: ButtonCommand
  manualAssistanceLevelCount?: number
  disabled?: boolean
  onChange: (command: ButtonCommand) => Promise<void>
}

const commandTypes = new Set(BUTTON_COMMAND_CATALOGUE.map((spec) => spec.type))

const isCommandType = (
  value: string
): value is Exclude<ButtonCommandType, "unassigned"> =>
  commandTypes.has(value as (typeof BUTTON_COMMAND_CATALOGUE)[number]["type"])

export const ButtonCommandEditor = ({
  buttonIndex,
  command,
  manualAssistanceLevelCount,
  disabled = false,
  onChange,
}: ButtonCommandEditorProps) => {
  const spec = command === null ? undefined : buttonCommandSpec(command.type)

  const commit = async (nextCommand: ButtonCommand) => {
    try {
      await onChange(nextCommand)
    } catch {
      return
    }
  }

  return (
    <div className="grid gap-3">
      <div className="grid gap-1.5">
        <Label htmlFor={`button-${buttonIndex}-command`}>Command</Label>
        <Select
          value={command?.type ?? "unassigned"}
          items={commandTypeOptions}
          disabled={disabled}
          onValueChange={(value) => {
            if (value === null) return
            if (value === "unassigned") {
              void commit(null)
            } else if (isCommandType(value) && value !== command?.type) {
              void commit(defaultCommandForType(value))
            }
          }}
        >
          <SelectTrigger
            id={`button-${buttonIndex}-command`}
            className="w-full"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {commandTypeOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {command !== null && spec !== undefined
        ? spec.fields.map((field) => {
            const fieldId = `button-${buttonIndex}-${field.name}`
            const currentValue = Reflect.get(command, field.name)
            if (field.kind === "integer") {
              return (
                <ManualAssistanceSlider
                  key={field.name}
                  id={fieldId}
                  label={field.label}
                  level={Number(currentValue)}
                  levelCount={manualAssistanceLevelCount}
                  disabled={disabled}
                  onCommit={(level) =>
                    commit(commandWithField(command, field.name, level))
                  }
                />
              )
            }

            const options =
              field.kind === "boolean"
                ? [
                    { value: "true", label: "Enabled", raw: true },
                    { value: "false", label: "Disabled", raw: false },
                  ]
                : field.values.map((value) => ({
                    value: String(value),
                    label: sentenceLabel(value),
                    raw: value,
                  }))
            return (
              <div key={field.name} className="grid gap-1.5">
                <Label htmlFor={fieldId}>{field.label}</Label>
                <Select
                  value={String(currentValue)}
                  items={options}
                  disabled={disabled}
                  onValueChange={(value) => {
                    const selected = options.find(
                      (option) => option.value === value
                    )
                    if (selected !== undefined) {
                      void commit(
                        commandWithField(command, field.name, selected.raw)
                      )
                    }
                  }}
                >
                  <SelectTrigger id={fieldId} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {options.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )
          })
        : null}
    </div>
  )
}
