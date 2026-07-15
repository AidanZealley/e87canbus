import { CableIcon, CircleXIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Spinner } from "@/components/ui/spinner"
import type { LiveConnectionStatus } from "@/live/live-store"

type ConnectionBadgeProps = {
  connectionState: LiveConnectionStatus
}

const stateStyles: Record<LiveConnectionStatus, string> = {
  connected: "bg-green-600 text-green-50",
  connecting: "bg-foreground text-background",
  disconnected: "bg-red-600 text-red-50",
  reconnecting: "bg-amber-600 text-amber-50",
  synchronizing: "bg-amber-600 text-amber-50",
  incompatible: "bg-red-600 text-red-50",
}

export const ConnectionBadge = ({ connectionState }: ConnectionBadgeProps) => {
  const label =
    connectionState === "connected"
      ? "Connected"
      : connectionState === "connecting"
        ? "Connecting"
        : connectionState === "synchronizing"
          ? "Synchronizing"
          : connectionState === "reconnecting"
            ? "Reconnecting"
            : connectionState === "incompatible"
              ? "Incompatible"
              : "Disconnected"

  return (
    <Badge className={stateStyles[connectionState]}>
      {connectionState === "connected" ? (
        <CableIcon data-icon="inline-start" />
      ) : connectionState === "disconnected" ||
        connectionState === "incompatible" ? (
        <CircleXIcon data-icon="inline-start" />
      ) : (
        <Spinner data-icon="inline-start" />
      )}
      {label}
    </Badge>
  )
}
