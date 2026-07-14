import { CableIcon, RefreshCcwIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { SimulatorConnectionState } from "../../connection"

type ConnectionBadgeProps = {
  connectionState: SimulatorConnectionState
}

const stateStyles: Record<SimulatorConnectionState, string> = {
  connected:
    "border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  connecting:
    "border-amber-500/30 bg-amber-500/15 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  reconnecting:
    "border-destructive/30 bg-destructive/10 text-destructive dark:bg-destructive/20",
}

export const ConnectionBadge = ({ connectionState }: ConnectionBadgeProps) => {
  const connected = connectionState === "connected"
  const Icon = connected ? CableIcon : RefreshCcwIcon
  const label =
    connectionState === "connected"
      ? "Connected"
      : connectionState === "connecting"
        ? "Connecting"
        : "Reconnecting"

  return (
    <Badge variant="outline" className={stateStyles[connectionState]}>
      <Icon
        data-icon="inline-start"
        className={connected ? "" : "animate-spin"}
      />
      {label}
    </Badge>
  )
}
