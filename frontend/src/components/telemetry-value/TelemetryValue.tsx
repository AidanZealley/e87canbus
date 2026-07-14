import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export type TelemetryValueProps = {
  label: string
  value: string | number | null
  unit?: string
  status?: string
  className?: string
}

export const TelemetryValue = ({
  label,
  value,
  unit,
  status,
  className,
}: TelemetryValueProps) => {
  const available = value !== null
  const statusText = status ?? (available ? "Available" : "Unavailable")

  return (
    <Card size="sm" className={className} aria-label={label}>
      <CardContent className="grid min-w-0 gap-1">
        <span className="truncate text-xs font-medium tracking-wider text-muted-foreground uppercase">
          {label}
        </span>
        <span
          className={cn(
            "flex min-w-0 items-baseline gap-1 text-3xl leading-none font-semibold tabular-nums",
            !available && "text-muted-foreground"
          )}
        >
          <span>{available ? value : "—"}</span>
          {available && unit ? (
            <span className="text-sm font-medium text-muted-foreground">
              {unit}
            </span>
          ) : null}
        </span>
        <span className="text-xs text-muted-foreground">{statusText}</span>
      </CardContent>
    </Card>
  )
}
