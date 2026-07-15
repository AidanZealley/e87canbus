import { afterEach, expect, it, vi } from "vitest"

import {
  setCoolantTemperature,
  setEngineRpm,
  setOilTemperature,
  silenceCoolantTemperature,
  silenceEngineRpm,
  silenceOilTemperature,
  tapButton,
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
    [
      "http://127.0.0.1:8000/api/dev/simulation/vehicle/rpm",
      "PUT",
      { rpm: 3500 },
    ],
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

it("sends one atomic button-tap command", async () => {
  const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }))
  vi.stubGlobal("fetch", fetchMock)

  await tapButton(3)

  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8000/api/dev/simulation/devices/button-pad/buttons/3/tap",
    expect.objectContaining({ method: "POST" })
  )
})
