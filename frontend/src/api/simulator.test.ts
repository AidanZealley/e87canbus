import { afterEach, expect, it, vi } from "vitest"

import {
  setCoolantTemperature,
  setDeviceStatus,
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
    ["http://127.0.0.1:8000/api/dev/simulation/vehicle/rpm", "PUT", { rpm: 3500 }],
    [
      "http://127.0.0.1:8000/api/dev/simulation/vehicle/rpm/silence",
      "POST",
      undefined,
    ],
    [
      "http://127.0.0.1:8000/api/dev/simulation/vehicle/oil-temperature",
      "PUT",
      { temperature_c: 112.5 },
    ],
    [
      "http://127.0.0.1:8000/api/dev/simulation/vehicle/oil-temperature/silence",
      "POST",
      undefined,
    ],
    [
      "http://127.0.0.1:8000/api/dev/simulation/vehicle/coolant-temperature",
      "PUT",
      { temperature_c: 98 },
    ],
    [
      "http://127.0.0.1:8000/api/dev/simulation/vehicle/coolant-temperature/silence",
      "POST",
      undefined,
    ],
  ])
})

it("sends the exact typed device status path and body", async () => {
  const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }))
  vi.stubGlobal("fetch", fetchMock)

  await setDeviceStatus("steering_controller", "degraded")

  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8000/api/dev/simulation/devices/steering_controller/status",
    {
      headers: { "Content-Type": "application/json" },
      method: "PUT",
      body: JSON.stringify({ status: "degraded" }),
    }
  )
})
