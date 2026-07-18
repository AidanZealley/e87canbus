import type {
  ApplicationSettingsResponse,
  TemperatureUnit,
  UpdateApplicationSettingsRequest,
} from "@/api/http/types.gen"
import {
  celsiusToFahrenheit,
  fahrenheitThresholdToCelsius,
} from "../car-layout/car-ui.ts"
import type { ApplicationSettingsDraft } from "./types"

const displayTemperature = (valueC: number, unit: TemperatureUnit) =>
  String(
    Math.round((unit === "f" ? celsiusToFahrenheit(valueC) : valueC) * 10) / 10
  )

export const settingsToDraft = (
  settings: ApplicationSettingsResponse
): ApplicationSettingsDraft => ({
  sourceRevision: settings.revision,
  speedUnit: settings.speed_unit,
  temperatureUnit: settings.temperature_unit,
  oilWarning: displayTemperature(
    settings.oil_warning_c,
    settings.temperature_unit
  ),
  oilCritical: displayTemperature(
    settings.oil_critical_c,
    settings.temperature_unit
  ),
  coolantWarning: displayTemperature(
    settings.coolant_warning_c,
    settings.temperature_unit
  ),
  coolantCritical: displayTemperature(
    settings.coolant_critical_c,
    settings.temperature_unit
  ),
  shiftStage1Rpm: String(settings.shift_stage_1_rpm),
  shiftStage2Rpm: String(settings.shift_stage_2_rpm),
  redlineRpm: String(settings.redline_rpm),
})

const temperatureFields = [
  "oilWarning",
  "oilCritical",
  "coolantWarning",
  "coolantCritical",
] as const

const parseDisplayTemperature = (value: string) => {
  if (value.trim() === "") return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export const changeDraftTemperatureUnit = (
  draft: ApplicationSettingsDraft,
  unit: TemperatureUnit
): ApplicationSettingsDraft => {
  if (unit === draft.temperatureUnit) return draft
  const next = { ...draft, temperatureUnit: unit }
  for (const field of temperatureFields) {
    const value = parseDisplayTemperature(draft[field])
    if (value === null) continue
    const canonicalC =
      draft.temperatureUnit === "f"
        ? fahrenheitThresholdToCelsius(value)
        : Math.round(value * 10) / 10
    next[field] = displayTemperature(canonicalC, unit)
  }
  return next
}

export type SettingsValidation =
  | { request: UpdateApplicationSettingsRequest; error: null }
  | { request: null; error: string }

export const validateSettingsDraft = (
  draft: ApplicationSettingsDraft
): SettingsValidation => {
  const parsedTemperatures = temperatureFields.map((field) =>
    parseDisplayTemperature(draft[field])
  )
  if (parsedTemperatures.some((value) => value === null)) {
    return { request: null, error: "Enter a number for every temperature." }
  }
  const displayTemperatures = parsedTemperatures as [
    number,
    number,
    number,
    number,
  ]
  const [oilWarning, oilCritical, coolantWarning, coolantCritical] =
    displayTemperatures.map((value) =>
      draft.temperatureUnit === "f"
        ? fahrenheitThresholdToCelsius(value)
        : Math.round(value * 10) / 10
    )
  if (
    [oilWarning, oilCritical, coolantWarning, coolantCritical].some(
      (value) => value === undefined || value < -40 || value > 250
    )
  ) {
    return {
      request: null,
      error: "Temperature thresholds must be between -40°C and 250°C.",
    }
  }
  if ((oilWarning ?? 0) >= (oilCritical ?? 0)) {
    return {
      request: null,
      error: "Oil warning must be below oil critical.",
    }
  }
  if ((coolantWarning ?? 0) >= (coolantCritical ?? 0)) {
    return {
      request: null,
      error: "Coolant warning must be below coolant critical.",
    }
  }
  const rpmFields = [
    draft.shiftStage1Rpm,
    draft.shiftStage2Rpm,
    draft.redlineRpm,
  ]
  if (rpmFields.some((value) => !/^\d+$/.test(value.trim()))) {
    return { request: null, error: "RPM values must be whole numbers." }
  }
  const [shiftStage1Rpm, shiftStage2Rpm, redlineRpm] = rpmFields.map(Number)
  if (
    [shiftStage1Rpm, shiftStage2Rpm, redlineRpm].some(
      (value) => value === undefined || value < 1000 || value > 12000
    )
  ) {
    return { request: null, error: "RPM values must be from 1000 to 12000." }
  }
  if (!(
    (shiftStage1Rpm ?? 0) < (shiftStage2Rpm ?? 0) &&
    (shiftStage2Rpm ?? 0) < (redlineRpm ?? 0)
  )) {
    return {
      request: null,
      error: "Shift stage 1 must be below stage 2, and stage 2 below redline.",
    }
  }
  return {
    request: {
      expected_revision: draft.sourceRevision,
      speed_unit: draft.speedUnit,
      temperature_unit: draft.temperatureUnit,
      oil_warning_c: oilWarning!,
      oil_critical_c: oilCritical!,
      coolant_warning_c: coolantWarning!,
      coolant_critical_c: coolantCritical!,
      shift_stage_1_rpm: shiftStage1Rpm!,
      shift_stage_2_rpm: shiftStage2Rpm!,
      redline_rpm: redlineRpm!,
    },
    error: null,
  }
}

export const settingsDraftMatches = (
  draft: ApplicationSettingsDraft,
  settings: ApplicationSettingsResponse
) => {
  const result = validateSettingsDraft(draft)
  if (result.request === null) return false
  const editable = result.request
  return (
    draft.sourceRevision === settings.revision &&
    editable.speed_unit === settings.speed_unit &&
    editable.temperature_unit === settings.temperature_unit &&
    editable.oil_warning_c === settings.oil_warning_c &&
    editable.oil_critical_c === settings.oil_critical_c &&
    editable.coolant_warning_c === settings.coolant_warning_c &&
    editable.coolant_critical_c === settings.coolant_critical_c &&
    editable.shift_stage_1_rpm === settings.shift_stage_1_rpm &&
    editable.shift_stage_2_rpm === settings.shift_stage_2_rpm &&
    editable.redline_rpm === settings.redline_rpm
  )
}
