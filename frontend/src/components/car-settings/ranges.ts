import type { NumericSettingField } from "./types"

export type SettingRange = { min: number; max: number; step: number }

/**
 * Slider ranges are narrower than the backend's accepted bounds. They cover the
 * useful span for this car so a single sweep of a touch slider stays precise;
 * values already stored outside a range stay reachable because the slider
 * widens to include the current value.
 */
export const OIL_TEMPERATURE_RANGE_C: SettingRange = {
  min: 60,
  max: 180,
  step: 1,
}

export const COOLANT_TEMPERATURE_RANGE_C: SettingRange = {
  min: 60,
  max: 150,
  step: 1,
}

export const RPM_RANGE: SettingRange = { min: 1000, max: 9000, step: 50 }

export const SETTING_RANGES: Record<NumericSettingField, SettingRange> = {
  oilOperatingC: OIL_TEMPERATURE_RANGE_C,
  oilWarningC: OIL_TEMPERATURE_RANGE_C,
  oilCriticalC: OIL_TEMPERATURE_RANGE_C,
  coolantOperatingC: COOLANT_TEMPERATURE_RANGE_C,
  coolantWarningC: COOLANT_TEMPERATURE_RANGE_C,
  coolantCriticalC: COOLANT_TEMPERATURE_RANGE_C,
  shiftStage1Rpm: RPM_RANGE,
  shiftStage2Rpm: RPM_RANGE,
  redlineRpm: RPM_RANGE,
}

/**
 * Each chain must stay strictly ascending, so a field's usable bounds are
 * clamped by its neighbours rather than reported as a validation error.
 */
export const ASCENDING_SETTING_CHAINS: readonly (readonly NumericSettingField[])[] =
  [
    ["oilOperatingC", "oilWarningC", "oilCriticalC"],
    ["coolantOperatingC", "coolantWarningC", "coolantCriticalC"],
    ["shiftStage1Rpm", "shiftStage2Rpm", "redlineRpm"],
  ]
