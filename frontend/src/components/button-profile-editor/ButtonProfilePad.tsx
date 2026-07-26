import { useState } from "react"

import { ButtonBindingDialog } from "./ButtonBindingDialog"
import { ButtonProfileGrid } from "./ButtonProfileGrid"
import type { ButtonCommand, ButtonCommandSlots } from "./types"

type ButtonProfilePadProps = {
  slots: ButtonCommandSlots
  rgb: ReadonlyArray<readonly [number, number, number]>
  disabled?: boolean
  onChange: (index: number, command: ButtonCommand) => Promise<void>
}

export const ButtonProfilePad = ({
  slots,
  rgb,
  disabled = false,
  onChange,
}: ButtonProfilePadProps) => {
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  return (
    <>
      <ButtonProfileGrid
        slots={slots}
        rgb={rgb}
        disabled={disabled}
        onEdit={setEditingIndex}
      />
      {editingIndex !== null ? (
        <ButtonBindingDialog
          key={editingIndex}
          buttonIndex={editingIndex}
          command={slots[editingIndex]?.command ?? null}
          open
          onOpenChange={(open) => {
            if (!open) setEditingIndex(null)
          }}
          onApply={(command) => onChange(editingIndex, command)}
        />
      ) : null}
    </>
  )
}
