import { DropletIcon, WavesIcon } from "lucide-react"

import {
  COOLANT_MAXIMUM_TEMPERATURE_C,
  OIL_MAXIMUM_TEMPERATURE_C,
} from "@/components/car-layout/engine-temperature-scale"
import { DriveTemperatureGauge } from "@/components/drive-temperature-gauge"
import { RpmBar } from "@/components/rpm-bar"
import { TelemetryValue } from "@/components/telemetry-value"
import { useDriveTelemetry } from "../../use-drive-telemetry"
import { IndicatorLights } from "../indicator-lights"

export const ClassicDashboard = () => {
  const {
    settings,
    connected,
    lighting,
    speed,
    speedUnit,
    rpm,
    temperatureUnit,
    oil,
    coolant,
  } = useDriveTelemetry()

  return (
    <section
      className="grid h-full grid-rows-[minmax(0,1fr)_auto] gap-2 p-6"
      aria-labelledby="drive-title"
    >
      <h1 id="drive-title" className="sr-only">
        Drive
      </h1>
      <div className="flex flex-col gap-6">
        <IndicatorLights
          connected={connected}
          highBeamEnabled={lighting.high_beam_enabled}
        />
        <div className="flex flex-col gap-4">
          <RpmBar {...rpm} redlineRpm={settings.redline_rpm} />
          <TelemetryValue
            label="Speed"
            value={speed}
            unit={speedUnit}
            status={speed === null ? "Unavailable" : "Live"}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-12">
        <DriveTemperatureGauge
          icon={DropletIcon}
          label="Oil"
          value={oil.value}
          valueC={oil.valueC}
          unit={temperatureUnit}
          operatingTemperatureC={settings.oil_operating_c}
          maximumTemperatureC={OIL_MAXIMUM_TEMPERATURE_C}
          status={oil.status}
          severity={oil.severity}
        />
        <DriveTemperatureGauge
          icon={WavesIcon}
          label="Coolant"
          value={coolant.value}
          valueC={coolant.valueC}
          unit={temperatureUnit}
          operatingTemperatureC={settings.coolant_operating_c}
          maximumTemperatureC={COOLANT_MAXIMUM_TEMPERATURE_C}
          status={coolant.status}
          severity={coolant.severity}
        />
      </div>
    </section>
  )
}
