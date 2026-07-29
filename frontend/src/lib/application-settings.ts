import type { ApplicationSettingsResponse } from "@/api/http/types.gen"

export const DEFAULT_APPLICATION_SETTINGS: ApplicationSettingsResponse = {
  revision: 1,
  speed_unit: "mph",
  temperature_unit: "c",
  oil_operating_c: 110,
  oil_warning_c: 125,
  oil_critical_c: 140,
  coolant_operating_c: 95,
  coolant_warning_c: 110,
  coolant_critical_c: 120,
  shift_stage_1_rpm: 6800,
  shift_stage_2_rpm: 7000,
  redline_rpm: 7200,
  dashboard_id: "classic",
  updated_at: "1970-01-01T00:00:00.000000Z",
}
