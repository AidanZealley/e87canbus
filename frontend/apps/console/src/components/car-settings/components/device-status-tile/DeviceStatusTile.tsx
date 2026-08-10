import type { DeviceRegistryEntryState } from "@e87canbus/coordinator-client/api/live-contract.gen"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { deviceStatusPresentation, type DeviceStatusTone } from "./utils"

const DOT_CLASS: Record<DeviceStatusTone, string> = {
  positive: "bg-emerald-500",
  caution: "bg-amber-500",
  negative: "bg-destructive",
  neutral: "bg-muted-foreground/40",
}

const BADGE_VARIANT: Record<
  DeviceStatusTone,
  "secondary" | "warning" | "destructive" | "outline"
> = {
  positive: "secondary",
  caution: "warning",
  negative: "destructive",
  neutral: "outline",
}

export const DeviceStatusTile = ({
  device,
}: {
  device: DeviceRegistryEntryState
}) => {
  const { tone, label, detail } = deviceStatusPresentation(device)

  return (
    <Card size="sm" aria-label={device.label}>
      <CardHeader>
        <CardTitle className="flex min-w-0 items-center gap-2">
          <span
            className={cn("size-2 shrink-0 rounded-full", DOT_CLASS[tone])}
            aria-hidden="true"
          />
          <span className="min-w-0 truncate">{device.label}</span>
        </CardTitle>
        <CardAction>
          <Badge variant={BADGE_VARIANT[tone]}>{label}</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="grid gap-3">
        <p className="text-muted-foreground">{detail}</p>
        <dl className="grid grid-cols-3 gap-2 text-[0.625rem] text-muted-foreground">
          <div className="grid min-w-0 gap-0.5">
            <dt>Source</dt>
            <dd className="truncate font-medium text-foreground capitalize">
              {device.source_mode}
            </dd>
          </div>
          <div className="grid min-w-0 gap-0.5">
            <dt>Protocol</dt>
            <dd className="truncate font-medium text-foreground tabular-nums">
              {device.protocol_version === null
                ? "-"
                : `v${device.protocol_version}`}
            </dd>
          </div>
          <div className="grid min-w-0 gap-0.5">
            <dt>Device</dt>
            <dd className="truncate font-medium text-foreground tabular-nums">
              {device.device_id}
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  )
}
