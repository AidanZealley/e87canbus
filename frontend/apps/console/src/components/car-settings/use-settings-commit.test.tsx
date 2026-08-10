// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { PropsWithChildren } from "react"
import { afterEach, expect, test, vi } from "vitest"

import { DEFAULT_APPLICATION_SETTINGS } from "@e87canbus/coordinator-client/application-settings"
import { snapshot } from "@e87canbus/coordinator-client/live/test-fixtures"
import { useLiveStore } from "@e87canbus/coordinator-client/live/live-store"

const mocks = vi.hoisted(() => ({ update: vi.fn() }))

vi.mock(
  "@e87canbus/coordinator-client/api/http/@tanstack/react-query.gen",
  () => ({
    getApplicationSettingsQueryKey: () => ["application-settings"],
    updateApplicationSettingsMutation: () => ({ mutationFn: mocks.update }),
  })
)

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

import { useSettingsCommit } from "./use-settings-commit"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  useLiveStore.getState().reset()
})

test("does not defer a disconnected settings edit until synchronization returns", async () => {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  })
  const wrapper = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  useLiveStore.getState().applySnapshot(snapshot("boot", 1))
  const { result } = renderHook(
    () => useSettingsCommit(DEFAULT_APPLICATION_SETTINGS),
    { wrapper }
  )

  act(() => useLiveStore.getState().transportDisconnected())
  await act(() => result.current.commit({ speedUnit: "kmh" }))
  expect(mocks.update).not.toHaveBeenCalled()

  act(() => {
    useLiveStore.getState().transportConnected(true)
    useLiveStore.getState().applySnapshot(snapshot("boot", 2))
  })
  expect(result.current.canCommit).toBe(true)
  expect(mocks.update).not.toHaveBeenCalled()
})

test("admits only one revisioned settings write at a time", async () => {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  })
  const wrapper = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  let finishUpdate!: () => void
  mocks.update.mockReturnValue(
    new Promise((resolve) => {
      finishUpdate = () =>
        resolve({ ...DEFAULT_APPLICATION_SETTINGS, revision: 2 })
    })
  )
  useLiveStore.getState().applySnapshot(snapshot("boot", 1))
  const { result } = renderHook(
    () => useSettingsCommit(DEFAULT_APPLICATION_SETTINGS),
    { wrapper }
  )

  const first = result.current.commit({ speedUnit: "kmh" })
  await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1))
  await result.current.commit({ temperatureUnit: "f" })
  expect(mocks.update).toHaveBeenCalledTimes(1)

  finishUpdate()
  await first
})
