import { cn } from "@/lib/utils"

export type TelemetryValueProps = {
  value: string | number | null
  unit?: string
}

export const TelemetryValue = ({ value, unit }: TelemetryValueProps) => {
  const available = value !== null

  return (
    <div
      className={cn(
        "flex items-baseline gap-1 text-[20rem] leading-none tabular-nums",
        !available && "text-muted-foreground"
      )}
    >
      <span>{available ? value : "—"}</span>
      {available && unit ? (
        <span className="text-4xl font-semibold text-muted-foreground uppercase">
          {unit}
        </span>
      ) : null}
    </div>
  )
}
