import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { ButtonCommandSlots } from "./types"
import { commandLabel } from "./utils"

type ButtonProfileGridProps = {
  slots: ButtonCommandSlots
  rgb: ReadonlyArray<readonly [number, number, number]>
  onEdit: (index: number) => void
}

export const ButtonProfileGrid = ({
  slots,
  rgb,
  onEdit,
}: ButtonProfileGridProps) => (
  <div className="grid grid-cols-4 gap-2" aria-label="Editable button pad">
    {slots.map((command, index) => {
      const color = rgb[index] ?? [0, 0, 0]
      return (
        <Button
          key={index}
          type="button"
          variant="secondary"
          className={cn(
            "relative aspect-square h-auto min-h-16 flex-col gap-1 overflow-hidden rounded-3xl border-2 p-2",
            command === null && "border-dashed text-muted-foreground"
          )}
          style={{
            borderColor: `rgb(${color.join(" ")})`,
            boxShadow: `inset 0 0 12px rgb(${color.join(" ")} / 0.22)`,
          }}
          aria-label={`Edit button ${index}: ${commandLabel(command)}`}
          onClick={() => onEdit(index)}
        >
          <span className="font-heading text-lg">{index}</span>
          <span className="line-clamp-2 text-center text-[0.65rem] leading-tight sm:text-xs">
            {commandLabel(command)}
          </span>
        </Button>
      )
    })}
  </div>
)
