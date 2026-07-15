import type { EngineTelemetryStatus } from "@/components/simulator-workbench/types"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { TemperatureSeverity } from "@/components/car-layout/car-ui"

export type TemperatureGaugeProps = {
  label: string
  value: number | null
  unit: "°C" | "°F"
  status: EngineTelemetryStatus
  severity: TemperatureSeverity
  className?: string
}

const severityLabel: Record<TemperatureSeverity, string> = {
  normal: "Normal",
  warning: "Warning",
  critical: "Critical",
  unavailable: "Unavailable",
}

export const TemperatureGauge = ({
  label,
  value,
  unit,
  status,
  severity,
  className,
}: TemperatureGaugeProps) => {
  const available = value !== null && severity !== "unavailable"
  const unavailableLabel = status === "stale" ? "Stale" : "Unavailable"
  const displayStatus = available ? severityLabel[severity] : unavailableLabel

  return (
    <Card
      size="sm"
      className={cn(
        severity === "warning" && "ring-amber-500/60",
        severity === "critical" && "ring-destructive/70",
        className
      )}
      aria-label={label}
    >
      <CardContent className="grid min-w-0 gap-2">
        <div className="flex min-w-0 items-center justify-between gap-2">
          <span className="truncate text-xs font-medium tracking-wider text-muted-foreground uppercase">
            {label}
          </span>
          <Badge
            variant={severity === "critical" ? "destructive" : "outline"}
            className={cn(
              severity === "warning" &&
                "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
              severity === "unavailable" && "text-muted-foreground"
            )}
          >
            {displayStatus}
          </Badge>
        </div>
        <div
          className={cn(
            "flex items-baseline gap-1 text-3xl leading-none font-semibold tabular-nums",
            !available && "text-muted-foreground",
            severity === "warning" && "text-amber-700 dark:text-amber-300",
            severity === "critical" && "text-destructive"
          )}
        >
          <span>{available ? value : "—"}</span>
          {available ? (
            <span className="text-sm font-medium text-muted-foreground">
              {unit}
            </span>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}
