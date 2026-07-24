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
import {
  COOLANT_MAXIMUM_TEMPERATURE_C,
  OIL_MAXIMUM_TEMPERATURE_C,
} from "@/components/car-layout/engine-temperature-scale"
import { TelemetryValue } from "@/components/telemetry-value"
import {
  Abs,
  Battery,
  CheckEngine,
  CoolantTemperature,
  Fuel,
  HighBeam,
  LowBeam,
  OilPressure,
  TirePressure,
  TractionControl,
  TurnSignalLeft,
  TurnSignalRight,
} from "@/icons"
import { useEffectiveApplicationSettings } from "@/lib/application-settings-query"
import { cn } from "@/lib/utils"
import { useLiveStore } from "@/live/live-store"

export const CarDrive = () => {
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

  return (
    <section
      className="grid h-full grid-rows-[minmax(0,1fr)_auto] gap-2 p-6"
      aria-labelledby="drive-title"
    >
      <h1 id="drive-title" className="sr-only">
        Drive
      </h1>
      <div className="flex flex-col gap-6">
        <div
          className="flex w-full items-center justify-between"
          role="status"
          aria-label="Indicator lights"
        >
          <TurnSignalLeft
            aria-label="Left indicator"
            className="size-6 text-muted-foreground/20"
          />
          <div className="flex items-center gap-4">
            <LowBeam
              aria-label="Dipped beam"
              className="size-6 text-muted-foreground/20"
            />
            <HighBeam
              aria-label={
                connected && lighting.high_beam_enabled
                  ? "High beam on"
                  : "High beam off"
              }
              className={cn(
                "size-6 transition-colors",
                connected && lighting.high_beam_enabled
                  ? "text-blue-500"
                  : "text-muted-foreground/20"
              )}
            />
            <CheckEngine
              aria-label="Engine warning"
              className="size-6 text-muted-foreground/20"
            />
            <Abs
              aria-label="ABS warning"
              className="size-6 text-muted-foreground/20"
            />
            <TirePressure
              aria-label="Tyre pressure warning"
              className="size-6 text-muted-foreground/20"
            />
            <TractionControl
              aria-label="Traction control warning"
              className="size-6 text-muted-foreground/20"
            />
            <OilPressure
              aria-label="Oil pressure warning"
              className="size-6 text-muted-foreground/20"
            />
            <CoolantTemperature
              aria-label="Coolant temperature warning"
              className="size-6 text-muted-foreground/20"
            />
            <Battery
              aria-label="Battery warning"
              className="size-6 text-muted-foreground/20"
            />
            <Fuel
              aria-label="Low fuel warning"
              className="size-6 text-muted-foreground/20"
            />
          </div>
          <TurnSignalRight
            aria-label="Right indicator"
            className="size-6 text-muted-foreground/20"
          />
        </div>
        <div className="flex flex-col gap-4">
          <RpmBar {...rpm} redlineRpm={settings.redline_rpm} />
          <TelemetryValue
            label="Speed"
            value={speed}
            unit={settings.speed_unit === "mph" ? "mph" : "km/h"}
            status={speed === null ? "Unavailable" : "Live"}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-12">
        <DriveTemperatureGauge
          icon={DropletIcon}
          label="Oil temperature"
          value={presentTemperature(connected ? oilTelemetry.value : null)}
          valueC={connected ? oilTelemetry.value : null}
          unit={temperatureUnit}
          operatingTemperatureC={settings.oil_operating_c}
          maximumTemperatureC={OIL_MAXIMUM_TEMPERATURE_C}
          status={connected ? oilTelemetry.status : "stale"}
          severity={oilSeverity}
        />
        <DriveTemperatureGauge
          icon={WavesIcon}
          label="Coolant temperature"
          value={presentTemperature(connected ? coolantTelemetry.value : null)}
          valueC={connected ? coolantTelemetry.value : null}
          unit={temperatureUnit}
          operatingTemperatureC={settings.coolant_operating_c}
          maximumTemperatureC={COOLANT_MAXIMUM_TEMPERATURE_C}
          status={connected ? coolantTelemetry.status : "stale"}
          severity={coolantSeverity}
        />
      </div>
    </section>
  )
}
