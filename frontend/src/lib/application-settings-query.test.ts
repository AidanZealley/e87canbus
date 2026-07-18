import assert from "node:assert/strict"
import { it } from "vitest"

import {
  getApplicationSettings,
  updateApplicationSettings,
} from "../api/http/sdk.gen.ts"
import type {
  ApplicationSettingsResponse,
  UpdateApplicationSettingsRequest,
} from "../api/http/types.gen.ts"
import {
  resolveEffectiveApplicationSettings,
} from "./application-settings-query.ts"
import { DEFAULT_APPLICATION_SETTINGS } from "./application-settings.ts"

const updateRequest: UpdateApplicationSettingsRequest = {
  expected_revision: 1,
  speed_unit: "kmh",
  temperature_unit: "f",
  oil_warning_c: 124.5,
  oil_critical_c: 135,
  coolant_warning_c: 105,
  coolant_critical_c: 115,
  shift_stage_1_rpm: 6800,
  shift_stage_2_rpm: 7000,
  redline_rpm: 7200,
}

const committedSettings: ApplicationSettingsResponse = {
  ...DEFAULT_APPLICATION_SETTINGS,
  ...updateRequest,
  revision: 2,
  updated_at: "2026-07-14T12:30:00.000000Z",
}

it("generated settings SDK uses the configured base URL and request body", async () => {
  const calls: Request[] = []
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (input, init) => {
    calls.push(input instanceof Request ? input : new Request(input, init))
    return new Response(JSON.stringify(committedSettings), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })
  }
  try {
    assert.deepEqual(await getApplicationSettings(), committedSettings)
    assert.deepEqual(
      await updateApplicationSettings({ body: updateRequest }),
      committedSettings
    )
  } finally {
    globalThis.fetch = originalFetch
  }

  assert.equal(calls[0]?.url, "http://127.0.0.1:8000/api/settings")
  assert.equal(calls[1]?.url, "http://127.0.0.1:8000/api/settings")
  assert.equal(calls[1]?.method, "PUT")
  assert.deepEqual(await calls[1]?.clone().json(), updateRequest)
})

it("generated settings SDK throws the typed problem response", async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        error: {
          code: "settings_revision_conflict",
          message: "stale settings",
          current_revision: 2,
        },
      }),
      { status: 409, headers: { "Content-Type": "application/json" } }
    )
  try {
    await assert.rejects(
      updateApplicationSettings({ body: updateRequest }),
      (error: unknown) =>
        typeof error === "object" &&
        error !== null &&
        "error" in error &&
        (error as { error: { code: string } }).error.code ===
          "settings_revision_conflict"
    )
  } finally {
    globalThis.fetch = originalFetch
  }
})

it("effective settings expose fallback and persistence fault separately", () => {
  assert.deepEqual(resolveEffectiveApplicationSettings(undefined, false), {
    settings: DEFAULT_APPLICATION_SETTINGS,
    isAuthoritative: false,
    persistenceFault: false,
    canSave: false,
  })
  assert.deepEqual(resolveEffectiveApplicationSettings(undefined, true), {
    settings: DEFAULT_APPLICATION_SETTINGS,
    isAuthoritative: false,
    persistenceFault: true,
    canSave: false,
  })
  assert.deepEqual(
    resolveEffectiveApplicationSettings(committedSettings, true),
    {
      settings: committedSettings,
      isAuthoritative: true,
      persistenceFault: false,
      canSave: true,
    }
  )
})
