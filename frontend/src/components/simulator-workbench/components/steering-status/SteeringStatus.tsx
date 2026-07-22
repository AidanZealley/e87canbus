import { GaugeIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { useLiveStore } from "@/live/live-store"
import { formatSteeringReason } from "../../utils"

export const SteeringStatus = () => {
  const vehicle = useLiveStore((state) => state.vehicle)
  const steering = useLiveStore((state) => state.steering)
  const controller = useLiveStore((state) => state.steering?.servotronic)
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  if (
    !synchronized ||
    steering === null ||
    controller === undefined ||
    controller === null
  )
    return null
  const isAuto = steering.mode === "auto"
  const physical = controller.active_curve_source !== null

  return (
    <section className="grid gap-4" aria-label="Servotronic steering assist">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="font-heading text-sm font-medium">Steering assist</h2>
          <p className="text-xs/relaxed text-muted-foreground">
            {physical ? "Physical controller telemetry" : "In-process actuator projection and watchdog"}
          </p>
        </div>
        <div>
          <GaugeIcon aria-hidden="true" />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between rounded-md bg-muted p-3">
          <span className="text-xs text-muted-foreground">Mode</span>
          <div className="flex items-center gap-2">
            {steering.maximum_assistance_active ? (
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
              {vehicle.speed_valid ? (
                `${vehicle.speed_kph.toFixed(1)} km/h`
              ) : (
                <Badge variant="outline">No speed data</Badge>
              )}
            </dd>
          </div>
          <div className="rounded-md border p-3">
            <dt className="text-xs text-muted-foreground">Manual level</dt>
            <dd className="font-heading text-base font-semibold">
              {steering.manual_assistance_level}
            </dd>
          </div>
          <div className="rounded-md border p-3">
            <dt className="text-xs text-muted-foreground">
              Effective assistance
            </dt>
            <dd className="font-heading text-base font-semibold">
              {controller.effective_assistance === null
                ? "Unavailable"
                : `${(controller.effective_assistance * 100).toFixed(0)}%`}
            </dd>
          </div>
          <div className="rounded-md border p-3">
            <dt className="text-xs text-muted-foreground">
              Last command reason
            </dt>
            <dd className="font-heading text-base font-semibold capitalize">
              {formatSteeringReason(controller.last_command_reason)}
            </dd>
          </div>
          <div className="col-span-2 rounded-md border p-3">
            <dt className="text-xs text-muted-foreground">
              Controller watchdog
            </dt>
            <dd className="font-heading text-base font-semibold">
              {controller.watchdog_timed_out ? (
                <Badge variant="destructive">
                  Timed out — effective assistance 0%
                </Badge>
              ) : (
                <Badge variant="outline">Command fresh</Badge>
              )}
            </dd>
          </div>
        </dl>
      </div>

      {physical ? (
        <p className="text-xs text-muted-foreground">
          Curve {controller.active_curve_source} · revision {controller.active_curve_revision ?? "unknown"} · PWM {controller.pwm_duty ?? "unknown"} · {controller.inhibit_reason ?? "unknown"}
        </p>
      ) : null}

      <p className="text-xs text-muted-foreground">
        Button 0 changes mode; 1/2 adjust; 3 toggles maximum assist.
      </p>
    </section>
  )
}
