import { AlertTriangleIcon, RadioIcon, WifiOffIcon } from "lucide-react"

import { useConsoleLiveStore } from "@/local-live/store"

export const CanActivityStatus = () => {
  const connection = useConsoleLiveStore((state) => state.connection)
  const can = useConsoleLiveStore((state) => state.can)

  let label = "K-CAN status unavailable"
  let Icon = WifiOffIcon
  let fault = true
  if (connection.synchronized) {
    if (can.fault !== null) {
      label = `K-CAN fault: ${can.fault}`
      Icon = AlertTriangleIcon
    } else if (!can.connected) {
      label = "K-CAN disconnected"
    } else {
      label =
        can.frames_received === 0
          ? "K-CAN connected, no frames observed"
          : `K-CAN connected, ${can.frames_received.toLocaleString()} frames received`
      Icon = RadioIcon
      fault = false
    }
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className={
        fault
          ? "flex items-center gap-1.5 px-2 py-1 text-xs text-destructive"
          : "flex items-center gap-1.5 px-2 py-1 text-xs text-muted-foreground"
      }
    >
      <Icon className="size-3.5" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}
