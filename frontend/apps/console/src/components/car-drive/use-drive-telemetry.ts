import {
  celsiusToFahrenheit,
  deriveRpmPresentation,
  kilometresPerHourToMilesPerHour,
  roundDisplayValue,
} from "@/components/car-layout/car-ui"
import { useTemperatureSeverity } from "@/components/car-layout/use-temperature-severity"
import { useEffectiveApplicationSettings } from "@e87canbus/coordinator-client/application-settings-query"
import { useLiveStore } from "@e87canbus/coordinator-client/live/live-store"

/**
 * The derivation every dashboard needs: live telemetry resolved against the
 * authoritative units and thresholds. Those settings describe the car and the
 * driver rather than any one dashboard, so each dashboard honours them and
 * differs only in what it draws. A dashboard wanting more than this reads the
 * live store directly; the store already carries the whole controller state.
 */
export const useDriveTelemetry = () => {
  const vehicle = useLiveStore((state) => state.vehicle)
  const rpmTelemetry = useLiveStore((state) => state.engine.rpm)
  const oilTelemetry = useLiveStore((state) => state.engine.oil_temperature_c)
  const coolantTelemetry = useLiveStore(
    (state) => state.engine.coolant_temperature_c
  )
  const connected = useLiveStore((state) => state.connection.synchronized)
  const lighting = useLiveStore((state) => state.lighting)
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

  return {
    settings,
    connected,
    lighting,
    speed,
    speedUnit: settings.speed_unit === "mph" ? "mph" : "km/h",
    rpm,
    temperatureUnit,
    oil: {
      value: presentTemperature(connected ? oilTelemetry.value : null),
      valueC: connected ? oilTelemetry.value : null,
      status: connected ? oilTelemetry.status : "stale",
      severity: oilSeverity,
    },
    coolant: {
      value: presentTemperature(connected ? coolantTelemetry.value : null),
      valueC: connected ? coolantTelemetry.value : null,
      status: connected ? coolantTelemetry.status : "stale",
      severity: coolantSeverity,
    },
  } as const
}
