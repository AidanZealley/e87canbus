import type { ApplicationSettingsResponse } from "@/api/http/types.gen"
import type {
  DeviceRegistryEntryState,
  EngineTelemetryValue,
  RuntimeFaultState,
  SteeringState,
} from "@/api/live-contract.gen"

export type ServotronicAvailability = {
  telemetry: boolean
  modeControl: boolean
  activation: boolean
  reason: string
}

export const deriveServotronicAvailability = ({
  synchronized,
  status,
  steering,
  steeringFault,
  adapterFault,
}: {
  synchronized: boolean
  status: DeviceRegistryEntryState["status"]
  steering: SteeringState | null
  steeringFault: RuntimeFaultState | null
  adapterFault: RuntimeFaultState | null
}): ServotronicAvailability => {
  const unavailable = (reason: string): ServotronicAvailability => ({
    telemetry: false,
    modeControl: false,
    activation: false,
    reason,
  })
  if (!synchronized || steering === null) {
    return unavailable("live steering state unavailable")
  }
  if (steeringFault !== null || adapterFault !== null) {
    return unavailable("servotronic output adapter is faulted")
  }
  if (status !== "active") {
    return unavailable(`servotronic controller is ${status}`)
  }
  return {
    telemetry: steering.servotronic !== null,
    modeControl: true,
    activation: steering.curve_activation_available,
    reason: "",
  }
}

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
  status: EngineTelemetryValue["status"]
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
  status: EngineTelemetryValue["status"]
  connected: boolean
  settings: Pick<
    ApplicationSettingsResponse,
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
