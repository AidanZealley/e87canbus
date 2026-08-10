import { useState } from "react"

import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"

type ManualAssistanceSliderProps = {
  id: string
  label: string
  level: number
  levelCount?: number
  disabled?: boolean
  onCommit: (level: number) => Promise<void>
}

const levelPercentage = (level: number, levelCount: number): number =>
  levelCount <= 1 ? 100 : (level * 100) / (levelCount - 1)

export const ManualAssistanceSlider = ({
  id,
  label,
  level,
  levelCount,
  disabled = false,
  onCommit,
}: ManualAssistanceSliderProps) => {
  const usableLevelCount =
    levelCount !== undefined && levelCount > 0 ? levelCount : undefined
  const savedPercentage =
    usableLevelCount === undefined
      ? null
      : levelPercentage(level, usableLevelCount)
  const [edit, setEdit] = useState({
    levelWhenEdited: level,
    levelCountWhenEdited: levelCount,
    percentage: savedPercentage ?? 0,
  })
  const draftPercentage =
    edit.levelWhenEdited === level && edit.levelCountWhenEdited === levelCount
      ? edit.percentage
      : (savedPercentage ?? 0)
  const setDraftPercentage = (percentage: number) =>
    setEdit({
      levelWhenEdited: level,
      levelCountWhenEdited: levelCount,
      percentage,
    })
  const labelId = `${id}-label`
  const helpId = `${id}-help`

  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between gap-3">
        <Label id={labelId}>{label}</Label>
        <output className="text-sm text-muted-foreground tabular-nums">
          {savedPercentage === null
            ? `Level ${level}`
            : `${Math.round(draftPercentage)}%`}
        </output>
      </div>
      {usableLevelCount === undefined ? (
        <p id={helpId} className="text-xs text-muted-foreground">
          Connect to the car to edit assistance levels.
        </p>
      ) : (
        <Slider
          min={0}
          max={100}
          step={usableLevelCount === 1 ? 100 : 100 / (usableLevelCount - 1)}
          value={[draftPercentage]}
          disabled={disabled || usableLevelCount === 1}
          getAriaLabel={() => label}
          getAriaValueText={(_formattedValue, value) =>
            `${Math.round(value)} percent`
          }
          onValueChange={(nextValue) =>
            setDraftPercentage(nextValue[0] ?? savedPercentage ?? 0)
          }
          onValueCommitted={(nextValue) => {
            const nextPercentage = nextValue[0]
            if (nextPercentage === undefined) return
            const nextLevel =
              usableLevelCount === 1
                ? 0
                : Math.round((nextPercentage * (usableLevelCount - 1)) / 100)
            if (nextLevel === level) return
            void onCommit(nextLevel).catch(() =>
              setDraftPercentage(savedPercentage ?? 0)
            )
          }}
        />
      )}
    </div>
  )
}
