import { cn } from "@/lib/utils"

export type TelemetryValueProps = {
  label: string
  value: string | number | null
  unit?: string
  status?: string
}

export const TelemetryValue = ({
  label,
  value,
  unit,
  status,
}: TelemetryValueProps) => {
  const available = value !== null
  const statusText = status ?? (available ? "Available" : "Unavailable")

  return (
    <div
      role="group"
      aria-label={label}
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
      <span className="sr-only">{statusText}</span>
    </div>
  )
}
