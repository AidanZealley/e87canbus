import { useState } from "react"

import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"

type ButtonBrightnessRangeProps = {
  id: string
  minimum: number
  maximum: number
  disabled?: boolean
  onCommit: (minimum: number, maximum: number) => Promise<void>
}

export const ButtonBrightnessRange = ({
  id,
  minimum,
  maximum,
  disabled = false,
  onCommit,
}: ButtonBrightnessRangeProps) => {
  const [edit, setEdit] = useState({
    minimumWhenEdited: minimum,
    maximumWhenEdited: maximum,
    values: [minimum, maximum] as readonly number[],
  })
  const values =
    edit.minimumWhenEdited === minimum && edit.maximumWhenEdited === maximum
      ? edit.values
      : [minimum, maximum]
  const setValues = (nextValues: readonly number[]) =>
    setEdit({
      minimumWhenEdited: minimum,
      maximumWhenEdited: maximum,
      values: nextValues,
    })
  const labelId = `${id}-label`

  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between gap-3">
        <Label id={labelId}>Brightness range</Label>
        <output className="text-sm text-muted-foreground tabular-nums">
          {values[0]}–{values[1]}
        </output>
      </div>
      <Slider
        min={0}
        max={255}
        step={1}
        value={values}
        disabled={disabled}
        getAriaLabel={(index) =>
          index === 0 ? "Minimum brightness" : "Maximum brightness"
        }
        getAriaValueText={(_formattedValue, value) =>
          `${value} of 255 brightness`
        }
        onValueChange={(nextValues) => setValues(nextValues)}
        onValueCommitted={(nextValues) => {
          const [nextMinimum, nextMaximum] = nextValues
          if (
            nextMinimum === undefined ||
            nextMaximum === undefined ||
            (nextMinimum === minimum && nextMaximum === maximum)
          ) {
            return
          }
          void onCommit(nextMinimum, nextMaximum).catch(() =>
            setValues([minimum, maximum])
          )
        }}
      />
    </div>
  )
}
