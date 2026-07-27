import assert from "node:assert/strict"
import { test } from "vitest"

import { DEFAULT_APPLICATION_SETTINGS } from "../../lib/application-settings.ts"
import { RPM_RANGE } from "./ranges.ts"
import {
  clampSettingValue,
  formatTemperature,
  settingBounds,
  settingsToValues,
  valuesToRequest,
} from "./utils.ts"

const values = settingsToValues(DEFAULT_APPLICATION_SETTINGS)

test("presents canonical Celsius in the selected display unit", () => {
  assert.equal(formatTemperature(values.oilWarningC, "c"), "125°C")
  assert.equal(formatTemperature(values.oilWarningC, "f"), "257°F")
  assert.equal(formatTemperature(values.coolantCriticalC, "f"), "248°F")
})

test("closes each slider in with the neighbours it must stay between", () => {
  assert.deepEqual(settingBounds(values, "oilOperatingC"), {
    min: 60,
    max: 124,
    step: 1,
  })
  assert.deepEqual(settingBounds(values, "oilWarningC"), {
    min: 111,
    max: 139,
    step: 1,
  })
  assert.deepEqual(settingBounds(values, "oilCriticalC"), {
    min: 126,
    max: 180,
    step: 1,
  })
  assert.deepEqual(settingBounds(values, "shiftStage2Rpm"), {
    min: 6850,
    max: 7150,
    step: RPM_RANGE.step,
  })
})

test("clamps and steps an edit so ordering can never be broken", () => {
  assert.equal(clampSettingValue(values, "oilOperatingC", 130), 124)
  assert.equal(clampSettingValue(values, "oilOperatingC", 20), 60)
  assert.equal(clampSettingValue(values, "shiftStage1Rpm", 6773), 6750)
  assert.equal(clampSettingValue(values, "redlineRpm", 99999), RPM_RANGE.max)
})

test("sends one canonical document with the revision it expects", () => {
  const request = valuesToRequest({ ...values, oilWarningC: 124 }, 3)

  assert.equal(Object.keys(request).length, 12)
  assert.equal(request.expected_revision, 3)
  assert.equal(request.oil_warning_c, 124)
  assert.equal(request.oil_operating_c, 110)
  assert.equal(request.redline_rpm, 7200)
})
