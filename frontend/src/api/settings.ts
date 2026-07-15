import { queryOptions } from "@tanstack/react-query"

import { ApiError, requestApi } from "./client.ts"

export type SpeedUnit = "mph" | "kmh"
export type TemperatureUnit = "c" | "f"

export type ApplicationSettings = {
  revision: number
  speed_unit: SpeedUnit
  temperature_unit: TemperatureUnit
  oil_warning_c: number
  oil_critical_c: number
  coolant_warning_c: number
  coolant_critical_c: number
  shift_stage_1_rpm: number
  shift_stage_2_rpm: number
  redline_rpm: number
  updated_at: string
}

export type UpdateApplicationSettingsRequest = Omit<
  ApplicationSettings,
  "revision" | "updated_at"
> & {
  expected_revision: number
}

export const DEFAULT_APPLICATION_SETTINGS: ApplicationSettings = {
  revision: 1,
  speed_unit: "mph",
  temperature_unit: "c",
  oil_warning_c: 125,
  oil_critical_c: 135,
  coolant_warning_c: 105,
  coolant_critical_c: 115,
  shift_stage_1_rpm: 6800,
  shift_stage_2_rpm: 7000,
  redline_rpm: 7200,
  updated_at: "1970-01-01T00:00:00.000000Z",
}

export const applicationSettingsQueryKey = ["application-settings"] as const

export const getApplicationSettings = () =>
  requestApi<ApplicationSettings>("/api/settings", "Settings")

export const updateApplicationSettings = (
  request: UpdateApplicationSettingsRequest
) =>
  requestApi<ApplicationSettings>("/api/settings", "Settings", {
    method: "PUT",
    body: JSON.stringify(request),
  })

export const applicationSettingsQueryOptions = () =>
  queryOptions({
    queryKey: applicationSettingsQueryKey,
    queryFn: getApplicationSettings,
  })

export { ApiError as SettingsApiError }
