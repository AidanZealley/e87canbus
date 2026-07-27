import type { SpeedUnit, TemperatureUnit } from "@/api/http/types.gen"

/** The editable half of the settings document, without revision metadata. */
export type ApplicationSettingsValues = {
  speedUnit: SpeedUnit
  temperatureUnit: TemperatureUnit
  oilOperatingC: number
  oilWarningC: number
  oilCriticalC: number
  coolantOperatingC: number
  coolantWarningC: number
  coolantCriticalC: number
  shiftStage1Rpm: number
  shiftStage2Rpm: number
  redlineRpm: number
}

export type TemperatureField =
  | "oilOperatingC"
  | "oilWarningC"
  | "oilCriticalC"
  | "coolantOperatingC"
  | "coolantWarningC"
  | "coolantCriticalC"

export type RpmField = "shiftStage1Rpm" | "shiftStage2Rpm" | "redlineRpm"

export type NumericSettingField = TemperatureField | RpmField
