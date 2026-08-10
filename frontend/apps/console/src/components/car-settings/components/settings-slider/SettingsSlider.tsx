import { useState } from "react"

import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import type { SettingRange } from "../../ranges"

type SettingsSliderProps = {
  label: string
  /** Distinguishes sliders that share a visible label across groups. */
  ariaLabel?: string
  value: number
  bounds: SettingRange
  disabled?: boolean
  format: (value: number) => string
  onCommit: (value: number) => Promise<void>
}

export const SettingsSlider = ({
  label,
  ariaLabel,
  value,
  bounds,
  disabled = false,
  format,
  onCommit,
}: SettingsSliderProps) => {
  // Track the drag locally so the readout follows the thumb, and drop it once
  // the commit settles so the saved value is the one on screen.
  const [drag, setDrag] = useState<number | null>(null)
  const displayed = drag ?? value
  // A stored value from outside the slider's usual span stays adjustable.
  const min = Math.min(bounds.min, displayed)
  const max = Math.max(bounds.max, displayed)

  return (
    <div className="grid gap-2">
      <div className="flex items-baseline justify-between gap-3">
        <Label>{label}</Label>
        <output className="font-heading text-xs/relaxed font-medium tabular-nums">
          {format(displayed)}
        </output>
      </div>
      <Slider
        min={min}
        max={max}
        step={bounds.step}
        value={[displayed]}
        disabled={disabled}
        getAriaLabel={() => ariaLabel ?? label}
        getAriaValueText={(_formatted, thumbValue) => format(thumbValue)}
        onValueChange={(next) => {
          const nextValue = next[0]
          if (nextValue !== undefined) setDrag(nextValue)
        }}
        onValueCommitted={(next) => {
          const nextValue = next[0]
          if (nextValue === undefined || nextValue === value) {
            setDrag(null)
            return
          }
          void onCommit(nextValue).finally(() => setDrag(null))
        }}
      />
      <div className="flex justify-between text-[0.625rem] text-muted-foreground tabular-nums">
        <span>{format(min)}</span>
        <span>{format(max)}</span>
      </div>
    </div>
  )
}
