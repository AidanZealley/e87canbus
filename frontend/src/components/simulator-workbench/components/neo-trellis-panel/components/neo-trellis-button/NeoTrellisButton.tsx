import type { CSSProperties } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type NeoTrellisButtonProps = {
  index: number
  rgb: readonly [red: number, green: number, blue: number]
  disabled: boolean
  onClick: (index: number) => void
}

export const NeoTrellisButton = ({
  index,
  rgb,
  disabled,
  onClick,
}: NeoTrellisButtonProps) => (
  <Button
    variant="outline"
    className={cn(
      "relative isolate aspect-square h-auto min-h-14 overflow-hidden rounded-4xl bg-transparent p-1 hover:bg-transparent",
      "border-[rgb(var(--button-led-rgb)/45%)]",
      "shadow-[inset_0_1px_1px_rgb(255_255_255/40%),inset_0_-4px_7px_rgb(0_0_0/16%),inset_0_0_0_3px_rgb(var(--button-led-rgb)/85%),0_4px_0_rgb(var(--button-led-rgb)/25%),0_9px_16px_rgb(15_23_42/16%)]",
      "[text-shadow:0_1px_1px_rgb(255_255_255/45%)]",
      "transition-[transform,box-shadow] duration-100 ease-out",
      "active:translate-y-0.5 active:scale-[0.99]",
      "active:shadow-[inset_0_4px_7px_rgb(0_0_0/22%),inset_0_-1px_1px_rgb(255_255_255/25%),inset_0_0_0_3px_rgb(var(--button-led-rgb)/65%),0_1px_1px_rgb(var(--button-led-rgb)/22%),0_3px_7px_rgb(15_23_42/12%)]"
    )}
    style={
      {
        "--button-led-rgb": rgb.join(" "),
      } as CSSProperties
    }
    aria-label={`Button ${index}`}
    disabled={disabled}
    onClick={() => onClick(index)}
  >
    <span
      aria-hidden="true"
      className="pointer-events-none absolute inset-0.75 z-0 rounded-[calc(var(--radius-4xl)-0.25rem)] bg-[radial-gradient(circle_at_30%_20%,rgb(255_255_255/10%),transparent_36%),linear-gradient(145deg,rgb(var(--button-led-rgb)/22%),var(--card))]"
    />
    <span
      aria-hidden="true"
      className="pointer-events-none absolute inset-0.75 z-0 rounded-[calc(var(--radius-4xl)-0.25rem)] bg-[radial-gradient(circle_at_30%_20%,rgb(255_255_255/5%),transparent_36%),linear-gradient(145deg,rgb(var(--button-led-rgb)/12%),var(--muted))] opacity-0 transition-opacity duration-100 ease-out group-hover/button:opacity-100"
    />
    <span
      aria-hidden="true"
      className="pointer-events-none absolute inset-0.75 z-0 rounded-[calc(var(--radius-4xl)-0.25rem)] bg-[radial-gradient(circle_at_30%_20%,rgb(255_255_255/5%),transparent_36%),linear-gradient(145deg,rgb(var(--button-led-rgb)/30%),var(--muted))] opacity-0 transition-opacity duration-100 ease-out group-active/button:opacity-100"
    />
    <span className="relative z-10 font-heading text-2xl transition-transform duration-100 ease-out group-active/button:translate-y-0.5">
      {index}
    </span>
  </Button>
)
