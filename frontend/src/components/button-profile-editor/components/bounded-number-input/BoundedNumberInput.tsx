import { useState } from "react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

type BoundedNumberInputProps = {
  id: string
  label: string
  value: number
  minimum?: number
  maximum?: number
  disabled?: boolean
  onCommit: (value: number) => Promise<void>
}

export const BoundedNumberInput = ({
  id,
  label,
  value,
  minimum,
  maximum,
  disabled = false,
  onCommit,
}: BoundedNumberInputProps) => {
  const [edit, setEdit] = useState({
    valueWhenEdited: value,
    draft: String(value),
  })
  const draft = edit.valueWhenEdited === value ? edit.draft : String(value)
  const setDraft = (nextDraft: string) =>
    setEdit({ valueWhenEdited: value, draft: nextDraft })

  const commit = async () => {
    const parsed = Number(draft)
    const valid =
      Number.isInteger(parsed) &&
      (minimum === undefined || parsed >= minimum) &&
      (maximum === undefined || parsed <= maximum)
    if (!valid) {
      setDraft(String(value))
      return
    }
    if (parsed === value) return
    try {
      await onCommit(parsed)
    } catch {
      setDraft(String(value))
    }
  }

  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="number"
        value={draft}
        min={minimum}
        max={maximum}
        step={1}
        required
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => void commit()}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur()
          if (event.key === "Escape") {
            setDraft(String(value))
            event.currentTarget.blur()
          }
        }}
      />
    </div>
  )
}
