import { AlertTriangleIcon, WifiOffIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { useEffectiveApplicationSettings } from "@/lib/application-settings-query"
import { useLiveStore } from "@/live/live-store"

export const CarStatusBanners = () => {
  const connection = useLiveStore((state) => state.connection)
  const settings = useEffectiveApplicationSettings()
  const connectionFault = !connection.synchronized
  const settingsFault = settings.persistenceFault
  if (!connectionFault && !settingsFault) return null

  return (
    <div className="grid shrink-0 gap-1 p-1 pb-0" aria-label="Car status">
      {connectionFault ? (
        <Alert variant="destructive">
          <WifiOffIcon />
          <AlertTitle>Live data unavailable</AlertTitle>
          <AlertDescription>
            {connection.status === "connecting"
              ? "Connecting to vehicle data."
              : (connection.error ?? "Reconnecting to vehicle data.")}
          </AlertDescription>
        </Alert>
      ) : null}
      {settingsFault ? (
        <Alert variant="destructive">
          <AlertTriangleIcon />
          <AlertTitle>Configuration unavailable</AlertTitle>
          <AlertDescription>Using compiled display defaults.</AlertDescription>
        </Alert>
      ) : null}
    </div>
  )
}
