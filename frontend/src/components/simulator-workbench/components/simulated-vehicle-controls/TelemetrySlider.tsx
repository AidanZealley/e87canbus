import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"

type TelemetrySliderProps = {
  id: string
  label: string
  unit: string
  minimum: number
  maximum: number
  step: number
  value: number
  disabled: boolean
  onValueChange: (value: number) => void
  onCommit: (value: number) => void
}

export const TelemetrySlider = ({
  id,
  label,
  unit,
  minimum,
  maximum,
  step,
  value: controlledValue,
  disabled,
  onValueChange,
  onCommit,
}: TelemetrySliderProps) => {
  const labelId = `${id}-label`

  const toBoundedValue = (nextValue: number) => {
    if (Number.isFinite(nextValue)) {
      return Math.min(maximum, Math.max(minimum, nextValue))
    }
    return controlledValue
  }

  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between gap-3">
        <Label id={labelId}>{label}</Label>
        <output className="text-sm tabular-nums text-muted-foreground">
          {controlledValue} {unit}
        </output>
      </div>
      <Slider
        min={minimum}
        max={maximum}
        step={step}
        value={[controlledValue]}
        disabled={disabled}
        aria-labelledby={labelId}
        onValueChange={(nextValue) =>
          onValueChange(
            toBoundedValue(Array.isArray(nextValue) ? nextValue[0] : nextValue)
          )
        }
        onValueCommitted={(nextValue) => {
          const committedValue = Array.isArray(nextValue)
            ? nextValue[0]
            : nextValue
          const boundedValue = toBoundedValue(committedValue)
          onValueChange(boundedValue)
          onCommit(boundedValue)
        }}
      />
    </div>
  )
}
