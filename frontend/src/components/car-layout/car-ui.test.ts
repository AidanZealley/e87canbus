import assert from "node:assert/strict"
import test from "node:test"

import { DEFAULT_APPLICATION_SETTINGS } from "../../lib/application-settings.ts"
import {
  celsiusToFahrenheit,
  deriveRpmPresentation,
  fahrenheitThresholdToCelsius,
  fahrenheitToCelsius,
  kilometresPerHourToMilesPerHour,
  roundDisplayValue,
  transitionTemperatureSeverity,
  type TemperatureSeverity,
} from "./car-ui.ts"

test("canonical conversions include negative values and whole-number display rounding", () => {
  assert.equal(kilometresPerHourToMilesPerHour(100), 62.137100000000004)
  assert.equal(kilometresPerHourToMilesPerHour(-10), -6.21371)
  assert.equal(celsiusToFahrenheit(-40), -40)
  assert.equal(celsiusToFahrenheit(0), 32)
  assert.equal(fahrenheitToCelsius(-40), -40)
  assert.equal(fahrenheitToCelsius(32), 0)
  assert.equal(roundDisplayValue(12.49), 12)
  assert.equal(roundDisplayValue(12.5), 13)
  assert.equal(roundDisplayValue(-12.6), -13)
})

test("Fahrenheit form thresholds round-trip to the nearest tenth Celsius", () => {
  const fahrenheit = celsiusToFahrenheit(124.6)
  assert.equal(fahrenheitThresholdToCelsius(fahrenheit), 124.6)
  assert.equal(fahrenheitThresholdToCelsius(-4), -20)
})

const severity = (
  previous: TemperatureSeverity,
  valueC: number | null,
  options: {
    status?: "valid" | "never_observed" | "stale"
    connected?: boolean
    thresholdsChanged?: boolean
  } = {}
) =>
  transitionTemperatureSeverity({
    previous,
    valueC,
    status: options.status ?? "valid",
    connected: options.connected ?? true,
    thresholds: { warningC: 100, criticalC: 110 },
    thresholdsChanged: options.thresholdsChanged,
  })

test("temperature severity promotes at exact thresholds", () => {
  assert.equal(severity("normal", 99.9), "normal")
  assert.equal(severity("normal", 100), "warning")
  assert.equal(severity("normal", 109.9), "warning")
  assert.equal(severity("normal", 110), "critical")
  assert.equal(severity("warning", 110), "critical")
})

test("temperature hysteresis holds exact boundaries and demotes in order", () => {
  assert.equal(severity("critical", 107), "critical")
  assert.equal(severity("critical", 106.9), "warning")
  assert.equal(severity("warning", 97), "warning")
  assert.equal(severity("warning", 96.9), "normal")
  assert.equal(severity("critical", 96), "normal")
})

test("invalid, stale, missing and disconnected readings clear severity immediately", () => {
  assert.equal(severity("critical", 120, { status: "stale" }), "unavailable")
  assert.equal(
    severity("warning", 105, { status: "never_observed" }),
    "unavailable"
  )
  assert.equal(severity("critical", null), "unavailable")
  assert.equal(severity("critical", 120, { connected: false }), "unavailable")
})

test("settings changes re-evaluate without retaining old hysteresis", () => {
  assert.equal(severity("warning", 108), "warning")
  assert.equal(
    transitionTemperatureSeverity({
      previous: "warning",
      valueC: 108,
      status: "valid",
      connected: true,
      thresholds: { warningC: 110, criticalC: 130 },
      thresholdsChanged: true,
    }),
    "normal"
  )
  assert.equal(
    transitionTemperatureSeverity({
      previous: "critical",
      valueC: 112,
      status: "valid",
      connected: true,
      thresholds: { warningC: 105, criticalC: 130 },
      thresholdsChanged: true,
    }),
    "warning"
  )
})

test("RPM stages cover every boundary and clamp only visual position", () => {
  const derive = (value: number | null, status = "valid" as const) =>
    deriveRpmPresentation({
      value,
      status,
      connected: true,
      settings: DEFAULT_APPLICATION_SETTINGS,
    })

  assert.deepEqual(derive(6799), {
    rpm: 6799,
    stage: "normal",
    position: 6799 / 7200,
  })
  assert.equal(derive(6800).stage, "stage_1")
  assert.equal(derive(7000).stage, "stage_2")
  assert.equal(derive(7200).stage, "redline")
  assert.deepEqual(derive(8000), {
    rpm: 8000,
    stage: "redline",
    position: 1,
  })
  assert.deepEqual(derive(-100), {
    rpm: -100,
    stage: "normal",
    position: 0,
  })
  assert.deepEqual(derive(null), {
    rpm: null,
    stage: "unavailable",
    position: 0,
  })
  assert.equal(
    deriveRpmPresentation({
      value: 7000,
      status: "stale",
      connected: true,
      settings: DEFAULT_APPLICATION_SETTINGS,
    }).stage,
    "unavailable"
  )
  assert.equal(
    deriveRpmPresentation({
      value: 7000,
      status: "valid",
      connected: false,
      settings: DEFAULT_APPLICATION_SETTINGS,
    }).stage,
    "unavailable"
  )
})
