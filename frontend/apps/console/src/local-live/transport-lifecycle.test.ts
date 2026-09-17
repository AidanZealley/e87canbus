import { afterEach, expect, it, vi } from "vitest"

const generatedStreamOperation = vi.hoisted(() => vi.fn())

vi.mock("@/api/console-host", () => ({
  streamConsoleLiveApiLiveGet: generatedStreamOperation,
}))

import type { streamConsoleLiveApiLiveGet } from "@/api/console-host"
import {
  disposeConsoleLiveTransport,
  startConsoleLiveTransport,
} from "./transport"

type StreamOptions = NonNullable<
  Parameters<typeof streamConsoleLiveApiLiveGet>[0]
>

const blockUntilAborted = async function* (signal?: AbortSignal) {
  await new Promise<void>((resolve) => {
    if (signal?.aborted) resolve()
    else signal?.addEventListener("abort", () => resolve(), { once: true })
  })
  yield* []
}

afterEach(() => {
  disposeConsoleLiveTransport()
  generatedStreamOperation.mockReset()
})

it("keeps one local stream and releases it for hot replacement", async () => {
  generatedStreamOperation.mockImplementation(
    async (options?: StreamOptions) => ({
      stream: blockUntilAborted(options?.signal ?? undefined),
    })
  )

  startConsoleLiveTransport()
  startConsoleLiveTransport()

  await vi.waitFor(() =>
    expect(generatedStreamOperation).toHaveBeenCalledTimes(1)
  )
  const firstSignal = generatedStreamOperation.mock.calls[0][0]
    .signal as AbortSignal
  expect(firstSignal.aborted).toBe(false)

  disposeConsoleLiveTransport()
  expect(firstSignal.aborted).toBe(true)

  startConsoleLiveTransport()
  await vi.waitFor(() =>
    expect(generatedStreamOperation).toHaveBeenCalledTimes(2)
  )
})
