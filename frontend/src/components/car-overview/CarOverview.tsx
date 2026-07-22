import { useQuery } from "@tanstack/react-query"

import { listSteeringProfilesOptions } from "@/api/http/@tanstack/react-query.gen"
import {
  celsiusToFahrenheit,
  roundDisplayValue,
} from "@/components/car-layout/car-ui"
import { DeviceStatusFooter } from "@/components/device-status-footer"
import { TemperatureGauge } from "@/components/temperature-gauge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useEffectiveApplicationSettings } from "@/lib/application-settings-query"
import { useLiveStore } from "@/live/live-store"
import { useServotronicAvailability } from "@/components/car-layout/use-servotronic-availability"
import { useTemperatureSeverity } from "@/components/car-layout/use-temperature-severity"
import { activeProfileLabel, steeringModeLabel } from "./utils"

export const CarOverview = () => {
  const steering = useLiveStore((state) => state.steering)
  const servotronicRegistry = useLiveStore(
    (state) => state.devices.registry.servotronic_controller
  )
  const buttonPadRegistry = useLiveStore(
    (state) => state.devices.registry.button_pad
  )
  const oilTelemetry = useLiveStore((state) => state.engine.oil_temperature_c)
  const coolantTelemetry = useLiveStore(
    (state) => state.engine.coolant_temperature_c
  )
  const connected = useLiveStore((state) => state.connection.synchronized)
  const servotronic = useServotronicAvailability()
  const settings = useEffectiveApplicationSettings().settings
  const profiles = useQuery(listSteeringProfilesOptions())
  const oilSeverity = useTemperatureSeverity({
    telemetry: oilTelemetry,
    connected,
    thresholds: {
      warningC: settings.oil_warning_c,
      criticalC: settings.oil_critical_c,
    },
  })
  const coolantSeverity = useTemperatureSeverity({
    telemetry: coolantTelemetry,
    connected,
    thresholds: {
      warningC: settings.coolant_warning_c,
      criticalC: settings.coolant_critical_c,
    },
  })
  const temperatureUnit = settings.temperature_unit === "f" ? "°F" : "°C"
  const presentTemperature = (value: number | null) =>
    value === null
      ? null
      : roundDisplayValue(
          settings.temperature_unit === "f" ? celsiusToFahrenheit(value) : value
        )

  return (
    <section
      className="flex min-h-full flex-col gap-2 p-2"
      aria-labelledby="overview-title"
    >
      <h1 id="overview-title" className="sr-only">
        Overview
      </h1>
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] gap-2">
        <Card size="sm" aria-label="Steering status">
          <CardHeader>
            <CardTitle>Steering</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-x-4 gap-y-3">
            <StatusValue
              label="Mode"
              value={
                !connected || steering === null
                  ? "Unavailable"
                  : steeringModeLabel(steering)
              }
            />
            <StatusValue
              label="Assistance"
              value={
                servotronic.telemetry && steering?.servotronic
                  ? `${Math.round(steering.servotronic.effective_assistance * 100)}%`
                  : "Unavailable"
              }
            />
            {steering?.mode === "manual" ? (
              <StatusValue
                label="Manual setting"
                value={
                  servotronic.telemetry && steering.servotronic
                    ? `${Math.round(steering.servotronic.effective_assistance * 100)}%`
                    : "—"
                }
              />
            ) : null}
            <StatusValue
              label="Active profile"
              value={
                !connected || steering === null
                  ? "Active curve unavailable"
                  : activeProfileLabel({
                      steering,
                      profiles: profiles.data ?? [],
                      catalogAvailable:
                        !profiles.isError && profiles.data !== undefined,
                    })
              }
            />
          </CardContent>
        </Card>
        <div className="grid min-w-0 grid-rows-2 gap-2">
          <TemperatureGauge
            label="Oil temperature"
            value={presentTemperature(connected ? oilTelemetry.value : null)}
            unit={temperatureUnit}
            status={connected ? oilTelemetry.status : "stale"}
            severity={oilSeverity}
          />
          <TemperatureGauge
            label="Coolant temperature"
            value={presentTemperature(
              connected ? coolantTelemetry.value : null
            )}
            unit={temperatureUnit}
            status={connected ? coolantTelemetry.status : "stale"}
            severity={coolantSeverity}
          />
        </div>
      </div>
      <DeviceStatusFooter
        entries={connected ? [buttonPadRegistry, servotronicRegistry] : []}
      />
    </section>
  )
}

const StatusValue = ({ label, value }: { label: string; value: string }) => (
  <div className="min-w-0">
    <div className="text-xs tracking-wider text-muted-foreground uppercase">
      {label}
    </div>
    <div className="mt-1 text-xl leading-tight font-semibold wrap-break-word">
      {value}
    </div>
  </div>
)
