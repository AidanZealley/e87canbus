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
import {
  useApplicationSnapshot,
  useSteeringControllerSnapshot,
} from "../../query"
import { formatSteeringReason } from "../../utils"

export const SteeringStatus = () => {
  const application = useApplicationSnapshot()
  const controller = useSteeringControllerSnapshot()
  const isAuto = application.steering_mode === "auto"

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>Steering assist</CardTitle>
        <CardDescription>
          Application state and ideal controller projection
        </CardDescription>
        <CardAction>
          <GaugeIcon aria-hidden="true" />
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        <div className="flex items-center justify-between rounded-md bg-muted p-3">
          <span className="text-xs text-muted-foreground">Mode</span>
          <div className="flex items-center gap-2">
            {application.maximum_assistance_active ? (
              <Badge variant="destructive">Maximum</Badge>
            ) : null}
            <Badge variant={isAuto ? "default" : "secondary"}>
              {isAuto ? "Auto" : "Manual"}
            </Badge>
          </div>
        </div>
        <dl className="grid grid-cols-2 gap-2">
          <div className="rounded-md border p-3">
            <dt className="text-xs text-muted-foreground">Vehicle speed</dt>
            <dd className="font-heading text-base font-semibold">
              {application.speed_valid ? (
                `${application.vehicle_speed_kph.toFixed(1)} km/h`
              ) : (
                <Badge variant="outline">No speed data</Badge>
              )}
            </dd>
          </div>
          <div className="rounded-md border p-3">
            <dt className="text-xs text-muted-foreground">Manual level</dt>
            <dd className="font-heading text-base font-semibold">
              {application.manual_assistance_level}
            </dd>
          </div>
          <div className="rounded-md border p-3">
            <dt className="text-xs text-muted-foreground">
              Effective simulated assistance
            </dt>
            <dd className="font-heading text-base font-semibold">
              {(controller.effective_assistance * 100).toFixed(0)}%
            </dd>
          </div>
          <div className="rounded-md border p-3">
            <dt className="text-xs text-muted-foreground">Last command reason</dt>
            <dd className="font-heading text-base font-semibold capitalize">
              {formatSteeringReason(controller.last_command_reason)}
            </dd>
          </div>
          <div className="col-span-2 rounded-md border p-3">
            <dt className="text-xs text-muted-foreground">Controller watchdog</dt>
            <dd className="font-heading text-base font-semibold">
              {controller.watchdog_timed_out ? (
                <Badge variant="destructive">Timed out — effective assistance 0%</Badge>
              ) : (
                <Badge variant="outline">Command fresh</Badge>
              )}
            </dd>
          </div>
        </dl>
      </CardContent>

      <CardFooter>
        <p className="text-xs text-muted-foreground">
          Button 0 changes mode; 1/2 adjust; 3 toggles maximum assist.
        </p>
      </CardFooter>
    </Card>
  )
}
