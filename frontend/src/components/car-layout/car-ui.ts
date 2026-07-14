import type { ApplicationSettings } from "@/api/settings"
import type {
  ApplicationSnapshot,
  EngineTelemetryStatus,
} from "@/components/simulator-workbench/types"

export type TemperatureSeverity =
  "normal" | "warning" | "critical" | "unavailable"

export type RpmStage =
  "normal" | "stage_1" | "stage_2" | "redline" | "unavailable"

export type TemperatureThresholds = {
  warningC: number
  criticalC: number
}

export type RpmPresentation = {
  rpm: number | null
  stage: RpmStage
  position: number
}

export const kilometresPerHourToMilesPerHour = (value: number) =>
  value * 0.621371

export const celsiusToFahrenheit = (value: number) => (value * 9) / 5 + 32

export const fahrenheitToCelsius = (value: number) => ((value - 32) * 5) / 9

export const roundDisplayValue = (value: number) => Math.round(value)

export const fahrenheitThresholdToCelsius = (value: number) =>
  Math.round(fahrenheitToCelsius(value) * 10) / 10

export const transitionTemperatureSeverity = ({
  previous,
  valueC,
  status,
  connected,
  thresholds,
  thresholdsChanged = false,
}: {
  previous: TemperatureSeverity
  valueC: number | null
  status: EngineTelemetryStatus
  connected: boolean
  thresholds: TemperatureThresholds
  thresholdsChanged?: boolean
}): TemperatureSeverity => {
  if (!connected || status !== "valid" || valueC === null) {
    return "unavailable"
  }
  if (valueC >= thresholds.criticalC) return "critical"
  if (
    !thresholdsChanged &&
    previous === "critical" &&
    valueC >= thresholds.criticalC - 3
  ) {
    return "critical"
  }
  if (valueC >= thresholds.warningC) return "warning"

  if (
    !thresholdsChanged &&
    previous === "warning" &&
    valueC >= thresholds.warningC - 3
  ) {
    return "warning"
  }
  return "normal"
}

export const deriveRpmPresentation = ({
  value,
  status,
  connected,
  settings,
}: {
  value: number | null
  status: EngineTelemetryStatus
  connected: boolean
  settings: Pick<
    ApplicationSettings,
    "shift_stage_1_rpm" | "shift_stage_2_rpm" | "redline_rpm"
  >
}): RpmPresentation => {
  if (!connected || status !== "valid" || value === null) {
    return { rpm: null, stage: "unavailable", position: 0 }
  }

  const stage =
    value >= settings.redline_rpm
      ? "redline"
      : value >= settings.shift_stage_2_rpm
        ? "stage_2"
        : value >= settings.shift_stage_1_rpm
          ? "stage_1"
          : "normal"

  return {
    rpm: value,
    stage,
    position: Math.min(1, Math.max(0, value / settings.redline_rpm)),
  }
}

export const maskDisconnectedTelemetry = (
  application: ApplicationSnapshot,
  connected: boolean
): ApplicationSnapshot => {
  if (connected) return application
  return {
    ...application,
    speed_valid: false,
    engine: {
      rpm: { value: null, status: "stale" },
      oil_temperature_c: { value: null, status: "stale" },
      coolant_temperature_c: { value: null, status: "stale" },
    },
  }
}
