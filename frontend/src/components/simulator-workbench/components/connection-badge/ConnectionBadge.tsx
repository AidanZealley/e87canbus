import { CableIcon, CircleXIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Spinner } from "@/components/ui/spinner"
import type { SimulatorConnectionState } from "../../connection"

type ConnectionBadgeProps = {
  connectionState: SimulatorConnectionState
}

const stateStyles: Record<SimulatorConnectionState, string> = {
  connected: "bg-green-600 text-green-50",
  connecting: "bg-foreground text-background",
  disconnected: "bg-red-600 text-red-50",
  reconnecting: "bg-amber-600 text-amber-50",
}

export const ConnectionBadge = ({ connectionState }: ConnectionBadgeProps) => {
  const label =
    connectionState === "connected"
      ? "Connected"
      : connectionState === "connecting"
        ? "Connecting"
        : connectionState === "reconnecting"
          ? "Reconnecting"
          : "Disconnected"

  return (
    <Badge className={stateStyles[connectionState]}>
      {connectionState === "connected" ? (
        <CableIcon data-icon="inline-start" />
      ) : connectionState === "disconnected" ? (
        <CircleXIcon data-icon="inline-start" />
      ) : (
        <Spinner data-icon="inline-start" />
      )}
      {label}
    </Badge>
  )
}
