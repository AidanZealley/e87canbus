import { QueryClient } from "@tanstack/react-query"
import { afterEach, expect, it, vi } from "vitest"

const generatedStreamOperation = vi.hoisted(() => vi.fn())

vi.mock("@e87canbus/coordinator-client/api/http/sdk.gen", () => ({
  streamCoordinatorLiveApiLiveGet: generatedStreamOperation,
}))

import type { streamCoordinatorLiveApiLiveGet } from "@e87canbus/coordinator-client/api/http/sdk.gen"
import { disposeLiveTransport, startLiveTransport } from "./transport"

type StreamOptions = NonNullable<
  Parameters<typeof streamCoordinatorLiveApiLiveGet>[0]
>

const blockUntilAborted = async function* (signal?: AbortSignal) {
  await new Promise<void>((resolve) => {
    if (signal?.aborted) resolve()
    else signal?.addEventListener("abort", () => resolve(), { once: true })
  })
  yield* []
}

afterEach(() => {
  disposeLiveTransport()
  generatedStreamOperation.mockReset()
})

it("keeps one stream per module and releases it for hot replacement", async () => {
  generatedStreamOperation.mockImplementation(
    async (options?: StreamOptions) => ({
      stream: blockUntilAborted(options?.signal ?? undefined),
    })
  )
  const queryClient = new QueryClient()

  startLiveTransport(queryClient)
  startLiveTransport(queryClient)

  await vi.waitFor(() =>
    expect(generatedStreamOperation).toHaveBeenCalledTimes(1)
  )
  const firstSignal = generatedStreamOperation.mock.calls[0][0]
    .signal as AbortSignal
  expect(firstSignal.aborted).toBe(false)

  disposeLiveTransport()
  expect(firstSignal.aborted).toBe(true)

  startLiveTransport(queryClient)
  await vi.waitFor(() =>
    expect(generatedStreamOperation).toHaveBeenCalledTimes(2)
  )
})
