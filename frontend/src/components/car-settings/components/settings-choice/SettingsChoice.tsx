import { useId } from "react"
import type { LucideIcon } from "lucide-react"

import { Label } from "@/components/ui/label"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

export type SettingsChoiceOption<Value extends string> = {
  value: Value
  label: string
  icon?: LucideIcon
}

type SettingsChoiceProps<Value extends string> = {
  label: string
  value: Value
  options: readonly SettingsChoiceOption<Value>[]
  disabled?: boolean
  onChange: (value: Value) => void
}

export const SettingsChoice = <Value extends string>({
  label,
  value,
  options,
  disabled = false,
  onChange,
}: SettingsChoiceProps<Value>) => {
  const labelId = useId()
  const isOption = (candidate: string): candidate is Value =>
    options.some((option) => option.value === candidate)

  return (
    <div className="grid gap-2">
      <Label id={labelId}>{label}</Label>
      <ToggleGroup
        aria-labelledby={labelId}
        variant="outline"
        size="lg"
        spacing={0}
        value={[value]}
        disabled={disabled}
        // Re-pressing the active option clears the group; the setting keeps its
        // current value instead of becoming unset.
        onValueChange={(next) => {
          const selected = next.find((candidate) => candidate !== value)
          if (selected !== undefined && isOption(selected)) onChange(selected)
        }}
      >
        {options.map((option) => (
          <ToggleGroupItem key={option.value} value={option.value}>
            {option.icon === undefined ? null : (
              <option.icon aria-hidden="true" />
            )}
            {option.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  )
}
