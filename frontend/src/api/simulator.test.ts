import { afterEach, expect, it, vi } from "vitest"

import {
  setCoolantTemperature,
  setEngineRpm,
  setOilTemperature,
  silenceCoolantTemperature,
  silenceEngineRpm,
  silenceOilTemperature,
} from "./simulator"

afterEach(() => vi.unstubAllGlobals())

it("sends the exact engine telemetry command paths and bodies", async () => {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      void input
      void init
      return new Response("{}", { status: 200 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)

  await setEngineRpm(3500)
  await silenceEngineRpm()
  await setOilTemperature(112.5)
  await silenceOilTemperature()
  await setCoolantTemperature(98)
  await silenceCoolantTemperature()

  expect(
    fetchMock.mock.calls.map(([input, init]) => [
      input,
      init?.method,
      init?.body === undefined ? undefined : JSON.parse(String(init.body)),
    ])
  ).toEqual([
    ["http://127.0.0.1:8000/api/vehicle/rpm", "POST", { rpm: 3500 }],
    ["http://127.0.0.1:8000/api/vehicle/rpm/silence", "POST", undefined],
    [
      "http://127.0.0.1:8000/api/vehicle/oil-temperature",
      "POST",
      { temperature_c: 112.5 },
    ],
    [
      "http://127.0.0.1:8000/api/vehicle/oil-temperature/silence",
      "POST",
      undefined,
    ],
    [
      "http://127.0.0.1:8000/api/vehicle/coolant-temperature",
      "POST",
      { temperature_c: 98 },
    ],
    [
      "http://127.0.0.1:8000/api/vehicle/coolant-temperature/silence",
      "POST",
      undefined,
    ],
  ])
})
