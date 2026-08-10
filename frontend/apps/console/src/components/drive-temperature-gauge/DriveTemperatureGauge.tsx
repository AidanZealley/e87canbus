import { TriangleAlertIcon, type LucideIcon } from "lucide-react"

import type { TemperatureSeverity } from "@/components/car-layout/car-ui"
import type { EngineTelemetryValue } from "@e87canbus/coordinator-client/api/live-contract.gen"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"

export type DriveTemperatureGaugeProps = {
  icon: LucideIcon
  label: string
  value: number | null
  valueC: number | null
  unit: "°C" | "°F"
  operatingTemperatureC: number
  maximumTemperatureC: number
  status: EngineTelemetryValue["status"]
  severity: TemperatureSeverity
}

const severityLabel: Record<TemperatureSeverity, string> = {
  normal: "Normal",
  warning: "Warning",
  critical: "Critical",
  unavailable: "Unavailable",
}

const temperaturePosition = (
  valueC: number | null,
  operatingTemperatureC: number,
  maximumTemperatureC: number
) => {
  if (valueC === null) return 0
  const halfRange = Math.max(1, maximumTemperatureC - operatingTemperatureC)
  const minimumTemperatureC = operatingTemperatureC - halfRange
  return Math.min(
    100,
    Math.max(0, ((valueC - minimumTemperatureC) / (halfRange * 2)) * 100)
  )
}

export const DriveTemperatureGauge = ({
  icon: Icon,
  label,
  value,
  valueC,
  unit,
  operatingTemperatureC,
  maximumTemperatureC,
  status,
  severity,
}: DriveTemperatureGaugeProps) => {
  const available =
    value !== null && valueC !== null && severity !== "unavailable"
  const belowOperatingTemperature = available && valueC < operatingTemperatureC
  const displayStatus = available
    ? belowOperatingTemperature
      ? "Cold"
      : severityLabel[severity]
    : status === "stale"
      ? "Stale"
      : "Unavailable"
  const position = available
    ? temperaturePosition(valueC, operatingTemperatureC, maximumTemperatureC)
    : 0
  return (
    <div className="flex flex-col gap-3" aria-label={label}>
      <div className="flex flex-col gap-3">
        <div
          className={cn(
            "flex items-center justify-between gap-3",
            !available && "text-muted-foreground",
            belowOperatingTemperature && "text-blue-600 dark:text-blue-400",
            severity === "warning" && "text-amber-600 dark:text-amber-400",
            severity === "critical" && "text-destructive"
          )}
        >
          <Icon className="size-6 shrink-0" aria-hidden="true" />
          <div
            className={cn(
              "flex shrink-0 items-baseline gap-1 leading-none font-medium tabular-nums"
            )}
          >
            <span className="text-3xl">{available ? value : "-"}</span>
            {available ? (
              <span className="text-sm font-medium">{unit}</span>
            ) : null}
          </div>
        </div>

        <Progress
          value={position}
          aria-label={`${label} position`}
          aria-valuetext={
            available
              ? `${value}${unit}, ${displayStatus.toLowerCase()}; operating temperature is ${operatingTemperatureC}°C`
              : displayStatus
          }
          className={cn(
            "gap-0 **:data-[slot=progress-indicator]:bg-foreground/70 **:data-[slot=progress-track]:h-1 **:data-[slot=progress-track]:bg-muted/60",
            belowOperatingTemperature &&
              "**:data-[slot=progress-indicator]:bg-blue-500",
            severity === "warning" &&
              "**:data-[slot=progress-indicator]:bg-amber-500",
            severity === "critical" &&
              "**:data-[slot=progress-indicator]:bg-destructive",
            !available && "**:data-[slot=progress-indicator]:bg-transparent"
          )}
        />
      </div>

      <div className="flex w-full items-center justify-between gap-3">
        <span className="truncate font-semibold text-muted-foreground uppercase">
          {label}
        </span>
        <Badge
          className={cn(
            severity === "critical" && "motion-safe:animate-strobe"
          )}
          variant={
            severity === "critical"
              ? "destructive"
              : severity === "warning"
                ? "warning"
                : belowOperatingTemperature
                  ? "cold"
                  : "default"
          }
        >
          {severity === "critical" ? (
            <TriangleAlertIcon data-icon="inline-start" aria-hidden="true" />
          ) : null}
          {displayStatus}
        </Badge>
      </div>
    </div>
  )
}
