import type {
  ApplicationSettingsResponse,
  TemperatureUnit,
  UpdateApplicationSettingsRequest,
} from "@e87canbus/coordinator-client/api/http/types.gen"
import { celsiusToFahrenheit } from "../car-layout/car-ui"
import {
  ASCENDING_SETTING_CHAINS,
  SETTING_RANGES,
  type SettingRange,
} from "./ranges"
import type { ApplicationSettingsValues, NumericSettingField } from "./types"

export const settingsToValues = (
  settings: ApplicationSettingsResponse
): ApplicationSettingsValues => ({
  speedUnit: settings.speed_unit,
  temperatureUnit: settings.temperature_unit,
  oilOperatingC: settings.oil_operating_c,
  oilWarningC: settings.oil_warning_c,
  oilCriticalC: settings.oil_critical_c,
  coolantOperatingC: settings.coolant_operating_c,
  coolantWarningC: settings.coolant_warning_c,
  coolantCriticalC: settings.coolant_critical_c,
  shiftStage1Rpm: settings.shift_stage_1_rpm,
  shiftStage2Rpm: settings.shift_stage_2_rpm,
  redlineRpm: settings.redline_rpm,
  dashboardId: settings.dashboard_id,
})

export const valuesToRequest = (
  values: ApplicationSettingsValues,
  expectedRevision: number
): UpdateApplicationSettingsRequest => ({
  expected_revision: expectedRevision,
  speed_unit: values.speedUnit,
  temperature_unit: values.temperatureUnit,
  oil_operating_c: values.oilOperatingC,
  oil_warning_c: values.oilWarningC,
  oil_critical_c: values.oilCriticalC,
  coolant_operating_c: values.coolantOperatingC,
  coolant_warning_c: values.coolantWarningC,
  coolant_critical_c: values.coolantCriticalC,
  shift_stage_1_rpm: values.shiftStage1Rpm,
  shift_stage_2_rpm: values.shiftStage2Rpm,
  redline_rpm: values.redlineRpm,
  dashboard_id: values.dashboardId,
})

/**
 * The range a slider may move a field through: its own range, closed in by
 * whichever neighbours must stay below and above it. Ordering is enforced by
 * the control rather than reported as a validation error after the fact.
 */
export const settingBounds = (
  values: ApplicationSettingsValues,
  field: NumericSettingField
): SettingRange => {
  const range = SETTING_RANGES[field]
  const chain = ASCENDING_SETTING_CHAINS.find((candidate) =>
    candidate.includes(field)
  )
  if (chain === undefined) return range
  const index = chain.indexOf(field)
  const below = chain[index - 1]
  const above = chain[index + 1]
  const min =
    below === undefined
      ? range.min
      : Math.max(range.min, values[below] + range.step)
  const max =
    above === undefined
      ? range.max
      : Math.min(range.max, values[above] - range.step)
  return { min, max: Math.max(min, max), step: range.step }
}

export const clampSettingValue = (
  values: ApplicationSettingsValues,
  field: NumericSettingField,
  value: number
): number => {
  const bounds = settingBounds(values, field)
  const stepped = Math.round(value / bounds.step) * bounds.step
  return Math.min(Math.max(stepped, bounds.min), bounds.max)
}

export const temperatureUnitSuffix = (unit: TemperatureUnit) =>
  unit === "f" ? "°F" : "°C"

export const displayTemperature = (valueC: number, unit: TemperatureUnit) =>
  Math.round(unit === "f" ? celsiusToFahrenheit(valueC) : valueC)

export const formatTemperature = (valueC: number, unit: TemperatureUnit) =>
  `${displayTemperature(valueC, unit)}${temperatureUnitSuffix(unit)}`

export const formatRpm = (value: number) => `${value.toLocaleString()} rpm`
