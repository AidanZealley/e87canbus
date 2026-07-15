import { afterEach, expect, it, vi } from "vitest"

import { setMaximumAssistance, setSteeringMode } from "./commands"
import {
  activateSteeringCurve,
  type SteeringCurveDefinition,
  type StoredSteeringProfile,
} from "./steering"

afterEach(() => vi.unstubAllGlobals())

const acknowledgement = {
  accepted: true,
  boot_id: "boot-id",
  revision: 2,
} as const

it("sends exact idempotent set command paths and bodies", async () => {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      void input
      void init
      return new Response(JSON.stringify(acknowledgement), { status: 200 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)

  await setMaximumAssistance(true)
  await setSteeringMode("manual", 3)

  expect(fetchMock.mock.calls).toEqual([
    [
      "http://127.0.0.1:8000/api/commands/maximum-assistance",
      {
        headers: { "Content-Type": "application/json" },
        method: "PUT",
        body: JSON.stringify({ enabled: true }),
      },
    ],
    [
      "http://127.0.0.1:8000/api/commands/steering-mode",
      {
        headers: { "Content-Type": "application/json" },
        method: "PUT",
        body: JSON.stringify({ mode: "manual", manual_level: 3 }),
      },
    ],
  ])
})

it("separates saved-profile identity from unsaved curve activation", async () => {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      void input
      void init
      return new Response(JSON.stringify(acknowledgement), { status: 200 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)
  const definition = {
    schema_version: 1,
    points: [],
  } satisfies SteeringCurveDefinition
  const profile = {
    profile_id: "11111111-1111-4111-8111-111111111111",
    revision: 7,
  } as StoredSteeringProfile

  await activateSteeringCurve(definition, profile)
  await activateSteeringCurve(definition)

  expect(fetchMock.mock.calls.map(([path, init]) => [path, init])).toEqual([
    [
      "http://127.0.0.1:8000/api/commands/activate-steering-profile",
      {
        headers: { "Content-Type": "application/json" },
        method: "POST",
        body: JSON.stringify({
          profile_id: profile.profile_id,
          expected_revision: profile.revision,
        }),
      },
    ],
    [
      "http://127.0.0.1:8000/api/commands/steering-curve",
      {
        headers: { "Content-Type": "application/json" },
        method: "PUT",
        body: JSON.stringify({ definition }),
      },
    ],
  ])
})
