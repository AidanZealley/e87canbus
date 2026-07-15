import type { SpeedUnit, TemperatureUnit } from "@/api/settings"

export type ApplicationSettingsDraft = {
  sourceRevision: number
  speedUnit: SpeedUnit
  temperatureUnit: TemperatureUnit
  oilWarning: string
  oilCritical: string
  coolantWarning: string
  coolantCritical: string
  shiftStage1Rpm: string
  shiftStage2Rpm: string
  redlineRpm: string
}
