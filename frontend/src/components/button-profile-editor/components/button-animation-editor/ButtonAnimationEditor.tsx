import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  BUTTON_ANIMATION_SPEED_PRESETS,
  DEFAULT_BUTTON_ANIMATION_SPEED,
  type ButtonAnimationSpeed,
} from "../../constants"
import type { ButtonCommandSlot } from "../../types"
import { ButtonBrightnessRange } from "../button-brightness-range"

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

const animationSpeed = (
  animation: Exclude<ButtonAnimation, null>
): ButtonAnimationSpeed =>
  BUTTON_ANIMATION_SPEED_PRESETS.find((preset) =>
    animation.kind === "breathe"
      ? animation.period_ms === preset.breathePeriodMs
      : animation.on_ms === preset.blinkOnMs &&
        animation.off_ms === preset.blinkOffMs
  )?.value ?? DEFAULT_BUTTON_ANIMATION_SPEED

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
              const preset = BUTTON_ANIMATION_SPEED_PRESETS.find(
                ({ value: speed }) => speed === DEFAULT_BUTTON_ANIMATION_SPEED
              )
              if (preset === undefined) return
              void commit({
                kind: "breathe",
                period_ms: preset.breathePeriodMs,
                minimum: 8,
                maximum: 255,
              })
            }
            if (value === "blink" && animation?.kind !== "blink") {
              const preset = BUTTON_ANIMATION_SPEED_PRESETS.find(
                ({ value: speed }) => speed === DEFAULT_BUTTON_ANIMATION_SPEED
              )
              if (preset === undefined) return
              void commit({
                kind: "blink",
                on_ms: preset.blinkOnMs,
                off_ms: preset.blinkOffMs,
              })
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

      {animation !== null ? (
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor={`button-${buttonIndex}-animation-speed`}>
              Speed
            </Label>
            <Select
              value={animationSpeed(animation)}
              items={BUTTON_ANIMATION_SPEED_PRESETS}
              disabled={disabled}
              onValueChange={(value) => {
                const preset = BUTTON_ANIMATION_SPEED_PRESETS.find(
                  ({ value: speed }) => speed === value
                )
                if (preset === undefined) return
                if (animation.kind === "breathe") {
                  void commit({
                    ...animation,
                    period_ms: preset.breathePeriodMs,
                  })
                } else {
                  void commit({
                    ...animation,
                    on_ms: preset.blinkOnMs,
                    off_ms: preset.blinkOffMs,
                  })
                }
              }}
            >
              <SelectTrigger
                id={`button-${buttonIndex}-animation-speed`}
                className="w-full"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {BUTTON_ANIMATION_SPEED_PRESETS.map((preset) => (
                  <SelectItem key={preset.value} value={preset.value}>
                    {preset.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {animation.kind === "breathe" ? (
            <ButtonBrightnessRange
              id={`button-${buttonIndex}-breathe-brightness`}
              minimum={animation.minimum}
              maximum={animation.maximum}
              disabled={disabled}
              onCommit={(minimum, maximum) =>
                commit({ ...animation, minimum, maximum })
              }
            />
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
