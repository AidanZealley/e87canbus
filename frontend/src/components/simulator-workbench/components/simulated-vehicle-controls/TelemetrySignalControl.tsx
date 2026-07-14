import { useState, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import type { EngineTelemetryValue } from "../../types"

type TelemetrySignalControlProps = {
  id: string
  label: string
  unit: string
  minimum: number
  maximum: number
  step: number
  initialDraft: number
  telemetry: EngineTelemetryValue
  disabled: boolean
  onSet: (value: number) => void
  onSilence: () => void
}

export const TelemetrySignalControl = ({
  id,
  label,
  unit,
  minimum,
  maximum,
  step,
  initialDraft,
  telemetry,
  disabled,
  onSet,
  onSilence,
}: TelemetrySignalControlProps) => {
  const [draft, setDraft] = useState<number | "">(
    telemetry.value ?? initialDraft
  )

  const setBoundedDraft = (value: number) => {
    if (Number.isFinite(value)) {
      setDraft(Math.min(maximum, Math.max(minimum, value)))
    }
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (draft !== "") onSet(draft)
  }

  return (
    <form className="grid gap-3 border-t pt-4" onSubmit={handleSubmit}>
      <div className="flex items-end gap-2">
        <div className="grid min-w-0 flex-1 gap-1.5">
          <Label htmlFor={id}>{label}</Label>
          <div className="relative">
            <Input
              id={id}
              type="number"
              min={minimum}
              max={maximum}
              step={step}
              value={draft}
              disabled={disabled}
              className="pr-12"
              onChange={(event) => {
                if (event.target.value === "") setDraft("")
                else setBoundedDraft(event.target.valueAsNumber)
              }}
            />
            <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-xs text-muted-foreground">
              {unit}
            </span>
          </div>
        </div>
        <Button type="submit" disabled={disabled || draft === ""}>
          Set
        </Button>
      </div>

      <Slider
        min={minimum}
        max={maximum}
        step={step}
        value={[draft === "" ? minimum : draft]}
        disabled={disabled}
        aria-label={`Simulated ${label.toLowerCase()}`}
        onValueChange={(value) =>
          setBoundedDraft(Array.isArray(value) ? value[0] : value)
        }
      />

      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-muted-foreground" aria-live="polite">
          {formatTelemetryStatus(telemetry)}
        </span>
        <Button
          type="button"
          variant="outline"
          disabled={disabled || telemetry.status !== "valid"}
          onClick={onSilence}
        >
          Silence
        </Button>
      </div>
    </form>
  )
}

const formatTelemetryStatus = (telemetry: EngineTelemetryValue) => {
  switch (telemetry.status) {
    case "valid":
      return `Valid · ${telemetry.value ?? "—"}`
    case "never_observed":
      return "Never observed"
    case "stale":
      return "Stale"
  }
}
