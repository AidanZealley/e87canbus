import { DropletIcon, WavesIcon } from "lucide-react"

import {
  celsiusToFahrenheit,
  deriveRpmPresentation,
  kilometresPerHourToMilesPerHour,
  roundDisplayValue,
} from "@/components/car-layout/car-ui"
import { useTemperatureSeverity } from "@/components/car-layout/use-temperature-severity"
import { RpmBar } from "@/components/rpm-bar"
import { DriveTemperatureGauge } from "@/components/drive-temperature-gauge"
import { TelemetryValue } from "@/components/telemetry-value"
import { useEffectiveApplicationSettings } from "@/lib/application-settings-query"
import { useLiveStore } from "@/live/live-store"

const OIL_OPERATING_TEMPERATURE_C = 110
const COOLANT_OPERATING_TEMPERATURE_C = 95

export const CarDrive = () => {
  const vehicle = useLiveStore((state) => state.vehicle)
  const rpmTelemetry = useLiveStore((state) => state.engine.rpm)
  const oilTelemetry = useLiveStore((state) => state.engine.oil_temperature_c)
  const coolantTelemetry = useLiveStore(
    (state) => state.engine.coolant_temperature_c
  )
  const connected = useLiveStore((state) => state.connection.synchronized)
  const settings = useEffectiveApplicationSettings().settings
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
  const speedAvailable = vehicle.speed_valid && connected
  const speed = speedAvailable
    ? roundDisplayValue(
        settings.speed_unit === "mph"
          ? kilometresPerHourToMilesPerHour(vehicle.speed_kph)
          : vehicle.speed_kph
      )
    : null
  const rpm = deriveRpmPresentation({
    value: rpmTelemetry.value,
    status: rpmTelemetry.status,
    connected,
    settings,
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
      className="grid min-h-full grid-rows-[minmax(0,1fr)_auto] gap-2 p-12"
      aria-labelledby="drive-title"
    >
      <h1 id="drive-title" className="sr-only">
        Drive
      </h1>
      <div className="flex flex-col gap-12">
        <RpmBar {...rpm} redlineRpm={settings.redline_rpm} />
        <TelemetryValue
          label="Speed"
          value={speed}
          unit={settings.speed_unit === "mph" ? "mph" : "km/h"}
          status={speed === null ? "Unavailable" : "Live"}
        />
      </div>
      <div className="grid grid-cols-2 gap-12">
        <DriveTemperatureGauge
          icon={DropletIcon}
          label="Oil temperature"
          value={presentTemperature(connected ? oilTelemetry.value : null)}
          valueC={connected ? oilTelemetry.value : null}
          unit={temperatureUnit}
          operatingTemperatureC={OIL_OPERATING_TEMPERATURE_C}
          status={connected ? oilTelemetry.status : "stale"}
          severity={oilSeverity}
        />
        <DriveTemperatureGauge
          icon={WavesIcon}
          label="Coolant temperature"
          value={presentTemperature(connected ? coolantTelemetry.value : null)}
          valueC={connected ? coolantTelemetry.value : null}
          unit={temperatureUnit}
          operatingTemperatureC={COOLANT_OPERATING_TEMPERATURE_C}
          status={connected ? coolantTelemetry.status : "stale"}
          severity={coolantSeverity}
        />
      </div>
    </section>
  )
}
