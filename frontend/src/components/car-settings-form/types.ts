import type { SpeedUnit, TemperatureUnit } from "@/api/http/types.gen"

export type ApplicationSettingsDraft = {
  sourceRevision: number
  speedUnit: SpeedUnit
  temperatureUnit: TemperatureUnit
  oilOperating: string
  oilWarning: string
  oilCritical: string
  coolantOperating: string
  coolantWarning: string
  coolantCritical: string
  shiftStage1Rpm: string
  shiftStage2Rpm: string
  redlineRpm: string
}
