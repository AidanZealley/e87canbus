import { cn } from "@/lib/utils"
import { padSpeedDigits } from "../../utils"

type ClusterSpeedProps = {
  value: number | null
  unit: string
}

/**
 * The centre column: a single enormous numeral between two raked rules, with
 * the unit set small beneath it and ranged to its right edge.
 */
export const ClusterSpeed = ({ value, unit }: ClusterSpeedProps) => {
  const available = value !== null
  const { pad, digits } = padSpeedDigits(value)

  return (
    <div className="flex items-stretch gap-4">
      {/* The caption hangs off the numeral rather than sitting under it in
          flow, so only the figure's own box decides the readout's height. */}
      <div className="relative" role="status" aria-label="Road speed">
        <span
          className={cn(
            "text-[clamp(5rem,15vw,12rem)] leading-[0.8] font-medium tabular-nums",
            available ? "text-foreground" : "text-muted"
          )}
        >
          {/* Hidden from assistive tech: the pad is there to hold the width,
              and reading "zero two five" would be worse than reading "25". */}
          {pad === "" ? null : (
            <span aria-hidden="true" className="text-muted">
              {pad}
            </span>
          )}
          {digits}
        </span>
        <span className="absolute top-full -translate-y-2 right-0 text-[0.65rem] font-medium tracking-[0.25em] text-muted-foreground">
          {unit.toUpperCase()}
        </span>
        {available ? null : <span className="sr-only">Unavailable</span>}
      </div>
    </div>
  )
}
