import assert from "node:assert/strict"
import test from "node:test"

import { DEFAULT_APPLICATION_SETTINGS } from "../../lib/application-settings.ts"
import {
  changeDraftTemperatureUnit,
  settingsDraftMatches,
  settingsToDraft,
  validateSettingsDraft,
} from "./utils.ts"

test("initializes from authoritative values and preserves canonical meaning across unit changes", () => {
  const celsius = settingsToDraft(DEFAULT_APPLICATION_SETTINGS)
  const fahrenheit = changeDraftTemperatureUnit(celsius, "f")
  assert.equal(fahrenheit.oilWarning, "257")
  assert.equal(fahrenheit.coolantCritical, "239")

  const result = validateSettingsDraft(fahrenheit)
  assert.equal(result.error, null)
  assert.equal(result.request?.oil_warning_c, 125)
  assert.equal(result.request?.coolant_critical_c, 115)
  assert.equal(result.request?.temperature_unit, "f")

  assert.equal(
    changeDraftTemperatureUnit({ ...celsius, oilWarning: "" }, "f").oilWarning,
    ""
  )
})

test("rounds Fahrenheit edits to canonical tenths of Celsius on save", () => {
  const draft = changeDraftTemperatureUnit(
    settingsToDraft(DEFAULT_APPLICATION_SETTINGS),
    "f"
  )
  draft.oilWarning = "256.9"
  const result = validateSettingsDraft(draft)
  assert.equal(result.request?.oil_warning_c, 124.9)
})

test("matches backend temperature and RPM range and ordering rules", () => {
  const base = settingsToDraft(DEFAULT_APPLICATION_SETTINGS)
  assert.equal(settingsDraftMatches(base, DEFAULT_APPLICATION_SETTINGS), true)

  assert.match(
    validateSettingsDraft({ ...base, oilWarning: "" }).error ?? "",
    /number for every temperature/
  )
  assert.match(
    validateSettingsDraft({ ...base, oilWarning: "135" }).error ?? "",
    /Oil warning/
  )
  assert.match(
    validateSettingsDraft({ ...base, coolantCritical: "251" }).error ?? "",
    /-40°C and 250°C/
  )
  assert.match(
    validateSettingsDraft({ ...base, shiftStage1Rpm: "6800.5" }).error ?? "",
    /whole numbers/
  )
  assert.match(
    validateSettingsDraft({ ...base, shiftStage2Rpm: "7200" }).error ?? "",
    /stage 2 below redline/
  )
})
