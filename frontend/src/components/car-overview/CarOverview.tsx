import { useQuery } from "@tanstack/react-query"

import { listSteeringProfiles, steeringProfilesQueryKey } from "@/api/steering"
import { useCarData } from "@/components/car-layout"
import {
  celsiusToFahrenheit,
  roundDisplayValue,
} from "@/components/car-layout/car-ui"
import { DeviceStatusFooter } from "@/components/device-status-footer"
import { TemperatureGauge } from "@/components/temperature-gauge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { activeProfileLabel, steeringModeLabel } from "./utils"

export const CarOverview = () => {
  const {
    application,
    steeringController,
    connectionFault,
    devices,
    settings,
    oilSeverity,
    coolantSeverity,
  } = useCarData()
  const profiles = useQuery({
    queryKey: steeringProfilesQueryKey,
    queryFn: listSteeringProfiles,
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
            <StatusValue label="Mode" value={steeringModeLabel(application)} />
            <StatusValue
              label="Assistance"
              value={
                connectionFault
                  ? "— · Unavailable"
                  : `${Math.round(steeringController.effective_assistance * 100)}%`
              }
            />
            {application.steering_mode === "manual" ? (
              <StatusValue
                label="Manual setting"
                value={`Level ${application.manual_assistance_level + 1} of 8`}
              />
            ) : null}
            <StatusValue
              label="Active profile"
              value={activeProfileLabel({
                application,
                profiles: profiles.data ?? [],
                catalogAvailable:
                  !profiles.isError && profiles.data !== undefined,
              })}
            />
          </CardContent>
        </Card>
        <div className="grid min-w-0 grid-rows-2 gap-2">
          <TemperatureGauge
            label="Oil temperature"
            value={presentTemperature(
              application.engine.oil_temperature_c.value
            )}
            unit={temperatureUnit}
            status={application.engine.oil_temperature_c.status}
            severity={oilSeverity}
          />
          <TemperatureGauge
            label="Coolant temperature"
            value={presentTemperature(
              application.engine.coolant_temperature_c.value
            )}
            unit={temperatureUnit}
            status={application.engine.coolant_temperature_c.status}
            severity={coolantSeverity}
          />
        </div>
      </div>
      <DeviceStatusFooter devices={devices} />
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
