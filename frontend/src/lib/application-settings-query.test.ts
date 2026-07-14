import assert from "node:assert/strict"
import test from "node:test"
import { QueryClient } from "@tanstack/react-query"

import {
  applicationSettingsQueryKey,
  DEFAULT_APPLICATION_SETTINGS,
  getApplicationSettings,
  SettingsApiError,
  updateApplicationSettings,
  type ApplicationSettings,
  type UpdateApplicationSettingsRequest,
} from "../api/settings.ts"
import {
  resolveEffectiveApplicationSettings,
  saveApplicationSettings,
} from "./application-settings-query.ts"

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

const committedSettings: ApplicationSettings = {
  ...DEFAULT_APPLICATION_SETTINGS,
  speed_unit: updateRequest.speed_unit,
  temperature_unit: updateRequest.temperature_unit,
  oil_warning_c: updateRequest.oil_warning_c,
  oil_critical_c: updateRequest.oil_critical_c,
  coolant_warning_c: updateRequest.coolant_warning_c,
  coolant_critical_c: updateRequest.coolant_critical_c,
  shift_stage_1_rpm: updateRequest.shift_stage_1_rpm,
  shift_stage_2_rpm: updateRequest.shift_stage_2_rpm,
  redline_rpm: updateRequest.redline_rpm,
  revision: 2,
  updated_at: "2026-07-14T12:30:00.000000Z",
}

test("settings GET and PUT use the complete public request shapes", async () => {
  const calls: [RequestInfo | URL, RequestInit | undefined][] = []
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (input, init) => {
    calls.push([input, init])
    return new Response(JSON.stringify(committedSettings), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })
  }
  try {
    assert.deepEqual(await getApplicationSettings(), committedSettings)
    assert.deepEqual(
      await updateApplicationSettings(updateRequest),
      committedSettings
    )
  } finally {
    globalThis.fetch = originalFetch
  }

  assert.equal(calls[0]?.[0], "http://127.0.0.1:8000/api/settings")
  assert.equal(calls[0]?.[1]?.method, undefined)
  assert.equal(calls[1]?.[0], "http://127.0.0.1:8000/api/settings")
  assert.equal(calls[1]?.[1]?.method, "PUT")
  assert.deepEqual(JSON.parse(String(calls[1]?.[1]?.body)), updateRequest)
})

test("successful save replaces the settings cache with the committed response", async () => {
  const queryClient = new QueryClient()
  queryClient.setQueryData(
    applicationSettingsQueryKey,
    DEFAULT_APPLICATION_SETTINGS
  )
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () =>
    new Response(JSON.stringify(committedSettings), { status: 200 })
  try {
    const result = await saveApplicationSettings(queryClient, updateRequest)
    assert.deepEqual(result, committedSettings)
  } finally {
    globalThis.fetch = originalFetch
  }
  assert.deepEqual(
    queryClient.getQueryData(applicationSettingsQueryKey),
    committedSettings
  )
})

test("failed save keeps authoritative cached settings unchanged", async () => {
  const queryClient = new QueryClient()
  queryClient.setQueryData(
    applicationSettingsQueryKey,
    DEFAULT_APPLICATION_SETTINGS
  )
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
      { status: 409 }
    )
  try {
    await assert.rejects(
      saveApplicationSettings(queryClient, updateRequest),
      (error: unknown) =>
        error instanceof SettingsApiError &&
        error.code === "settings_revision_conflict" &&
        error.currentRevision === 2
    )
  } finally {
    globalThis.fetch = originalFetch
  }
  assert.deepEqual(
    queryClient.getQueryData(applicationSettingsQueryKey),
    DEFAULT_APPLICATION_SETTINGS
  )
})

test("effective settings expose fallback and persistence fault separately", () => {
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
