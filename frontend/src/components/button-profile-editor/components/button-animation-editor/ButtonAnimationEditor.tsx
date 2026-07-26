import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { ButtonCommandSlot } from "../../types"
import { BoundedNumberInput } from "../bounded-number-input"

type ButtonAnimation = NonNullable<ButtonCommandSlot>["animation"]

type ButtonAnimationEditorProps = {
  buttonIndex: number
  animation: ButtonAnimation
  disabled?: boolean
  onChange: (animation: ButtonAnimation) => Promise<void>
}

const animationOptions = [
  { value: "off", label: "Off" },
  { value: "breathe", label: "Breathe" },
  { value: "blink", label: "Blink" },
]

export const ButtonAnimationEditor = ({
  buttonIndex,
  animation,
  disabled = false,
  onChange,
}: ButtonAnimationEditorProps) => {
  const commit = async (nextAnimation: ButtonAnimation) => {
    try {
      await onChange(nextAnimation)
    } catch {
      return
    }
  }

  return (
    <div className="grid gap-3">
      <div className="grid gap-1.5">
        <Label htmlFor={`button-${buttonIndex}-animation`}>
          Active animation
        </Label>
        <Select
          value={animation?.kind ?? "off"}
          items={animationOptions}
          disabled={disabled}
          onValueChange={(value) => {
            if (value === "off") void commit(null)
            if (value === "breathe" && animation?.kind !== "breathe") {
              void commit({
                kind: "breathe",
                period_ms: 2000,
                minimum: 8,
                maximum: 255,
              })
            }
            if (value === "blink" && animation?.kind !== "blink") {
              void commit({ kind: "blink", on_ms: 400, off_ms: 400 })
            }
          }}
        >
          <SelectTrigger
            id={`button-${buttonIndex}-animation`}
            className="w-full"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {animationOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {animation?.kind === "breathe" ? (
        <div className="grid gap-3 sm:grid-cols-3">
          <BoundedNumberInput
            id={`button-${buttonIndex}-breathe-period`}
            label="Period (ms)"
            value={animation.period_ms}
            minimum={250}
            maximum={10000}
            disabled={disabled}
            onCommit={(period_ms) => commit({ ...animation, period_ms })}
          />
          <BoundedNumberInput
            id={`button-${buttonIndex}-breathe-minimum`}
            label="Minimum"
            value={animation.minimum}
            minimum={0}
            maximum={animation.maximum}
            disabled={disabled}
            onCommit={(minimum) => commit({ ...animation, minimum })}
          />
          <BoundedNumberInput
            id={`button-${buttonIndex}-breathe-maximum`}
            label="Maximum"
            value={animation.maximum}
            minimum={animation.minimum}
            maximum={255}
            disabled={disabled}
            onCommit={(maximum) => commit({ ...animation, maximum })}
          />
        </div>
      ) : null}

      {animation?.kind === "blink" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <BoundedNumberInput
            id={`button-${buttonIndex}-blink-on`}
            label="On (ms)"
            value={animation.on_ms}
            minimum={1}
            maximum={10000}
            disabled={disabled}
            onCommit={(on_ms) => commit({ ...animation, on_ms })}
          />
          <BoundedNumberInput
            id={`button-${buttonIndex}-blink-off`}
            label="Off (ms)"
            value={animation.off_ms}
            minimum={1}
            maximum={10000}
            disabled={disabled}
            onCommit={(off_ms) => commit({ ...animation, off_ms })}
          />
        </div>
      ) : null}
    </div>
  )
}
