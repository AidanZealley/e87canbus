import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { ledStyle } from "./led-style"

type NeoTrellisButtonProps = {
  index: number
  rgb: readonly [red: number, green: number, blue: number]
  animating: boolean
  disabled: boolean
  onClick: (index: number) => void
}

export const NeoTrellisButton = ({
  index,
  rgb,
  animating,
  disabled,
  onClick,
}: NeoTrellisButtonProps) => (
  <Button
    variant="secondary"
    className={cn(
      "relative isolate aspect-square h-auto min-h-14 overflow-hidden rounded-4xl p-1 data-[animating=true]:transition-none",
      "shadow-[inset_0_0_0_3px_rgb(var(--button-led-rgb)/var(--button-led-ring-alpha)),0_0_16px_rgb(var(--button-led-rgb)/var(--button-led-glow-alpha))]"
    )}
    style={ledStyle(rgb)}
    data-animating={animating ? "true" : undefined}
    aria-label={`Button ${index}`}
    disabled={disabled}
    onClick={() => onClick(index)}
  >
    <span
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 z-0 rounded-[inherit] bg-[linear-gradient(145deg,rgb(var(--button-led-rgb)/var(--button-led-cast-alpha)),transparent_65%)]"
    />
    <span className="relative z-10 font-heading text-2xl">{index}</span>
  </Button>
)
