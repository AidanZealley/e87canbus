import { DropletIcon, WavesIcon } from "lucide-react"

import { useCarData } from "@/components/car-layout"
import {
  celsiusToFahrenheit,
  deriveRpmPresentation,
  kilometresPerHourToMilesPerHour,
  roundDisplayValue,
} from "@/components/car-layout/car-ui"
import { RpmBar } from "@/components/rpm-bar"
import { DriveTemperatureGauge } from "@/components/drive-temperature-gauge"
import { TelemetryValue } from "@/components/telemetry-value"

const OIL_OPERATING_TEMPERATURE_C = 110
const COOLANT_OPERATING_TEMPERATURE_C = 95

export const CarDrive = () => {
  const {
    application,
    connectionFault,
    settings,
    oilSeverity,
    coolantSeverity,
  } = useCarData()
  const speedAvailable = application.speed_valid && !connectionFault
  const speed = speedAvailable
    ? roundDisplayValue(
        settings.speed_unit === "mph"
          ? kilometresPerHourToMilesPerHour(application.vehicle_speed_kph)
          : application.vehicle_speed_kph
      )
    : null
  const rpm = deriveRpmPresentation({
    value: application.engine.rpm.value,
    status: application.engine.rpm.status,
    connected: !connectionFault,
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
      <div className="flex flex-col gap-12">
        <RpmBar {...rpm} redlineRpm={settings.redline_rpm} />
        <TelemetryValue
          value={speed}
          unit={settings.speed_unit === "mph" ? "mph" : "km/h"}
        />
      </div>
      <div className="grid grid-cols-2 gap-12">
        <DriveTemperatureGauge
          icon={DropletIcon}
          label="Oil temperature"
          value={presentTemperature(application.engine.oil_temperature_c.value)}
          valueC={application.engine.oil_temperature_c.value}
          unit={temperatureUnit}
          operatingTemperatureC={OIL_OPERATING_TEMPERATURE_C}
          status={application.engine.oil_temperature_c.status}
          severity={oilSeverity}
        />
        <DriveTemperatureGauge
          icon={WavesIcon}
          label="Coolant temperature"
          value={presentTemperature(
            application.engine.coolant_temperature_c.value
          )}
          valueC={application.engine.coolant_temperature_c.value}
          unit={temperatureUnit}
          operatingTemperatureC={COOLANT_OPERATING_TEMPERATURE_C}
          status={application.engine.coolant_temperature_c.status}
          severity={coolantSeverity}
        />
      </div>
    </section>
  )
}
