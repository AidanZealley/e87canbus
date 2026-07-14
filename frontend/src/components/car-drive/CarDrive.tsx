import { useCarData } from "@/components/car-layout"
import {
  celsiusToFahrenheit,
  deriveRpmPresentation,
  kilometresPerHourToMilesPerHour,
  roundDisplayValue,
} from "@/components/car-layout/car-ui"
import { RpmBar } from "@/components/rpm-bar"
import { TemperatureGauge } from "@/components/temperature-gauge"
import { TelemetryValue } from "@/components/telemetry-value"

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
      className="grid min-h-full grid-rows-[minmax(0,1fr)_auto] gap-2 p-2"
      aria-labelledby="drive-title"
    >
      <h1 id="drive-title" className="sr-only">
        Drive
      </h1>
      <div className="grid min-h-0 grid-cols-[minmax(0,0.8fr)_minmax(0,1.65fr)] gap-2">
        <TelemetryValue
          label="Speed"
          value={speed}
          unit={settings.speed_unit === "mph" ? "mph" : "km/h"}
          status={speed === null ? "Unavailable" : "Live"}
          className="justify-center [&_[data-slot=card-content]]:grid [&_[data-slot=card-content]]:content-center [&_[data-slot=card-content]>span:nth-child(2)]:text-7xl"
        />
        <RpmBar
          {...rpm}
          redlineRpm={settings.redline_rpm}
          className="justify-center"
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <TemperatureGauge
          label="Oil temperature"
          value={presentTemperature(application.engine.oil_temperature_c.value)}
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
    </section>
  )
}
