import { DropletIcon, WavesIcon } from "lucide-react"

import {
  COOLANT_MAXIMUM_TEMPERATURE_C,
  OIL_MAXIMUM_TEMPERATURE_C,
} from "@/components/car-layout/engine-temperature-scale"
import { DriveTemperatureGauge } from "@/components/drive-temperature-gauge"
import { useDriveTelemetry } from "../../use-drive-telemetry"
import { IndicatorLights } from "../indicator-lights"
import { ClusterSpeed } from "./components/cluster-speed"
import { ClusterTachometer } from "./components/cluster-tachometer"

/**
 * A binnacle rather than a page, drawn entirely in theme tokens so it reads
 * the same way in either mode: the panel takes the background, the readouts
 * take the foreground, and anything shared drops in without adjustment.
 */
export const ClusterDashboard = () => {
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
      className="flex h-full flex-col justify-center bg-background p-6 [clip-path:polygon(0_0,100%_0,100%_calc(100%-1.75rem),calc(100%-1.75rem)_100%,1.75rem_100%,0_calc(100%-1.75rem))]"
      aria-labelledby="drive-title"
    >
      <h1 id="drive-title" className="sr-only">
        Drive
      </h1>

      {/* One banked instrument panel rather than widgets pushed to the edges:
          the tell-tales, the strip and the readouts stay together. */}
      <div className="mx-auto flex w-full max-w-360 flex-col gap-6">
        <IndicatorLights
          connected={connected}
          highBeamEnabled={lighting.high_beam_enabled}
        />

        <ClusterTachometer
          {...rpm}
          redlineRpm={settings.redline_rpm}
          shiftStage1Rpm={settings.shift_stage_1_rpm}
        />

        <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-end gap-16">
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

          <ClusterSpeed value={speed} unit={speedUnit} />

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
      </div>
    </section>
  )
}
