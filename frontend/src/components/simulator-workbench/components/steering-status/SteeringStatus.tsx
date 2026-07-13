import { GaugeIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { ApplicationSnapshot } from "../../types"

type SteeringStatusProps = {
  application?: ApplicationSnapshot
}

export const SteeringStatus = ({ application }: SteeringStatusProps) => {
  const isAuto = application?.steering_mode === "auto"

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>Steering assist</CardTitle>
        <CardDescription>Authoritative application state</CardDescription>
        <CardAction>
          <GaugeIcon aria-hidden="true" />
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        {application ? (
          <>
            <div className="flex items-center justify-between rounded-md bg-muted p-3">
              <span className="text-xs text-muted-foreground">Mode</span>
              <Badge variant={isAuto ? "default" : "secondary"}>
                {isAuto ? "Auto" : "Manual"}
              </Badge>
            </div>
            <dl className="grid grid-cols-2 gap-2">
              <div className="rounded-md border p-3">
                <dt className="text-xs text-muted-foreground">Vehicle speed</dt>
                <dd className="font-heading text-base font-semibold">
                  {application.vehicle_speed_kph.toFixed(1)} km/h
                </dd>
              </div>
              <div className="rounded-md border p-3">
                <dt className="text-xs text-muted-foreground">Manual level</dt>
                <dd className="font-heading text-base font-semibold">
                  {application.manual_assistance_level}
                </dd>
              </div>
            </dl>
          </>
        ) : (
          <p className="text-xs text-muted-foreground">
            Application state unavailable. Restart the simulator backend.
          </p>
        )}
      </CardContent>

      <CardFooter>
        <p className="text-xs text-muted-foreground">
          Press NeoTrellis button 0 to change mode.
        </p>
      </CardFooter>
    </Card>
  )
}
