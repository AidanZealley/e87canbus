import type { ButtonVisualState } from "../../button-led-presentation"
import type { ButtonCommandSlot, ButtonCommandSlots } from "../../types"
import { ButtonProfileItem } from "../button-profile-item"

type ButtonProfileListProps = {
  slots: ButtonCommandSlots
  visualStates: readonly ButtonVisualState[]
  disabled?: boolean
  onChange: (index: number, slot: ButtonCommandSlot) => Promise<void>
}

export const ButtonProfileList = ({
  slots,
  visualStates,
  disabled = false,
  onChange,
}: ButtonProfileListProps) => (
  <div className="grid gap-2" aria-label="Button configuration">
    {slots.map((slot, index) => (
      <ButtonProfileItem
        key={index}
        buttonIndex={index}
        slot={slot}
        visualState={visualStates[index] ?? "unassigned"}
        disabled={disabled}
        onChange={(nextSlot) => onChange(index, nextSlot)}
      />
    ))}
  </div>
)
