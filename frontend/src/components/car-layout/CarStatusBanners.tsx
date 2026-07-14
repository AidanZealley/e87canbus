import { AlertTriangleIcon, WifiOffIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { useCarData } from "./car-data-context"

export const CarStatusBanners = () => {
  const { connectionFault, connectionState, settingsFault } = useCarData()
  if (!connectionFault && !settingsFault) return null

  return (
    <div className="grid shrink-0 gap-1 p-1 pb-0" aria-label="Car status">
      {connectionFault ? (
        <Alert variant="destructive">
          <WifiOffIcon />
          <AlertTitle>Live data unavailable</AlertTitle>
          <AlertDescription>
            {connectionState === "connecting"
              ? "Connecting to vehicle data."
              : "Reconnecting to vehicle data."}
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
