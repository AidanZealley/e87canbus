import { describe, expect, it, vi } from "vitest"

import {
  streamConsoleLiveApiLiveGet,
  type StreamConsoleLiveApiLiveGetResponse,
} from "@/api/console-host"
import { consoleSnapshot } from "./test-fixtures"
import { useConsoleLiveStore } from "./store"
import { createConsoleLiveTransport } from "./transport"

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

const stream = async function* (
  values: readonly StreamConsoleLiveApiLiveGetResponse[]
) {
  yield* values
}

const snapshotThenBlock = async function* (
  framesReceived: number,
  signal?: AbortSignal
) {
  yield {
    type: "console.snapshot",
    data: consoleSnapshot(framesReceived),
  } as const
  yield* blockUntilAborted(signal)
}

const generatedFailure = async function* (
  options: StreamOptions | undefined,
  error: Error,
  values: readonly StreamConsoleLiveApiLiveGetResponse[] = []
) {
  yield* values
  options?.onSseError?.(error)
}

const deferred = () => {
  let resolve!: () => void
  const promise = new Promise<void>((complete) => {
    resolve = complete
  })
  return { promise, resolve }
}

describe("console SSE transport", () => {
  it("applies complete generated snapshots", async () => {
    useConsoleLiveStore.getState().reset()
    const operation = vi.fn(async (options?: StreamOptions) => {
      options?.onSseError?.(new Error("read failed"))
      return {
        stream: snapshotThenBlock(7, options?.signal ?? undefined),
      }
    }) as unknown as typeof streamConsoleLiveApiLiveGet

    const stop = createConsoleLiveTransport({
      streamOperation: operation,
      sleep: () => new Promise(() => undefined),
    })

    await vi.waitFor(() =>
      expect(useConsoleLiveStore.getState().can.frames_received).toBe(7)
    )
    expect(operation).toHaveBeenCalledTimes(1)
    expect(useConsoleLiveStore.getState().connection).toMatchObject({
      status: "connected",
      synchronized: true,
      error: null,
    })
    stop()
  })

  it("reconnects after clean EOF and replaces the complete projection", async () => {
    useConsoleLiveStore.getState().reset()
    let calls = 0
    const operation = vi.fn(async (options?: StreamOptions) => {
      calls += 1
      return {
        stream:
          calls === 1
            ? stream([{ type: "console.snapshot", data: consoleSnapshot(1) }])
            : snapshotThenBlock(2, options?.signal ?? undefined),
      }
    }) as unknown as typeof streamConsoleLiveApiLiveGet

    const stop = createConsoleLiveTransport({
      streamOperation: operation,
      reconnectDelayMs: 0,
      sleep: async () => undefined,
    })

    await vi.waitFor(() => expect(operation).toHaveBeenCalledTimes(2))
    await vi.waitFor(() =>
      expect(useConsoleLiveStore.getState().can.frames_received).toBe(2)
    )
    stop()
  })

  it("owns reconnection after a generated request failure", async () => {
    useConsoleLiveStore.getState().reset()
    const reconnect = deferred()
    let calls = 0
    const operationMock = vi.fn(async (options?: StreamOptions) => {
      calls += 1
      return {
        stream:
          calls === 1
            ? generatedFailure(options, new Error("fetch failed"))
            : snapshotThenBlock(2, options?.signal ?? undefined),
      }
    })
    const operation =
      operationMock as unknown as typeof streamConsoleLiveApiLiveGet
    const sleep = vi.fn(() => reconnect.promise)

    const stop = createConsoleLiveTransport({
      streamOperation: operation,
      sleep,
    })

    await vi.waitFor(() =>
      expect(useConsoleLiveStore.getState().connection.error).toBe(
        "fetch failed"
      )
    )
    expect(operation).toHaveBeenCalledTimes(1)
    expect(operationMock.mock.calls[0]?.[0]).toMatchObject({
      sseMaxRetryAttempts: 1,
    })
    expect(sleep).toHaveBeenCalledOnce()
    expect(sleep).toHaveBeenCalledWith(3_000)

    reconnect.resolve()
    await vi.waitFor(() => expect(operation).toHaveBeenCalledTimes(2))
    await vi.waitFor(() =>
      expect(useConsoleLiveStore.getState().can.frames_received).toBe(2)
    )
    expect(useConsoleLiveStore.getState().connection.error).toBeNull()
    expect(operationMock.mock.calls[1]?.[0]).toMatchObject({
      sseMaxRetryAttempts: 1,
    })
    stop()
  })

  it("retains valid state and reconnects after a generated read failure", async () => {
    useConsoleLiveStore.getState().reset()
    const reconnect = deferred()
    let calls = 0
    const operation = vi.fn(async (options?: StreamOptions) => {
      calls += 1
      return {
        stream:
          calls === 1
            ? generatedFailure(options, new Error("read failed"), [
                { type: "console.snapshot", data: consoleSnapshot(7) },
              ])
            : snapshotThenBlock(8, options?.signal ?? undefined),
      }
    }) as unknown as typeof streamConsoleLiveApiLiveGet
    const sleep = vi.fn(() => reconnect.promise)

    const stop = createConsoleLiveTransport({
      streamOperation: operation,
      sleep,
    })

    await vi.waitFor(() =>
      expect(useConsoleLiveStore.getState().connection.error).toBe(
        "read failed"
      )
    )
    expect(useConsoleLiveStore.getState().can.frames_received).toBe(7)
    expect(operation).toHaveBeenCalledTimes(1)
    expect(sleep).toHaveBeenCalledOnce()
    expect(sleep).toHaveBeenCalledWith(3_000)

    reconnect.resolve()
    await vi.waitFor(() => expect(operation).toHaveBeenCalledTimes(2))
    await vi.waitFor(() =>
      expect(useConsoleLiveStore.getState().can.frames_received).toBe(8)
    )
    expect(useConsoleLiveStore.getState().connection.error).toBeNull()
    stop()
  })

  it("aborts an idle connection and reconnects", async () => {
    useConsoleLiveStore.getState().reset()
    let calls = 0
    const operation = vi.fn(async (options?: StreamOptions) => {
      calls += 1
      return {
        stream:
          calls === 1
            ? blockUntilAborted(options?.signal ?? undefined)
            : snapshotThenBlock(2, options?.signal ?? undefined),
      }
    }) as unknown as typeof streamConsoleLiveApiLiveGet

    const stop = createConsoleLiveTransport({
      streamOperation: operation,
      idleTimeoutMs: 100,
      reconnectDelayMs: 0,
      sleep: async () => undefined,
    })

    await vi.waitFor(() =>
      expect(useConsoleLiveStore.getState().connection.synchronized).toBe(true)
    )
    expect(operation).toHaveBeenCalledTimes(2)
    stop()
  })

  it("counts keepalive comments as receive activity", async () => {
    useConsoleLiveStore.getState().reset()
    const operation = vi.fn(async (options?: StreamOptions) => {
      setTimeout(() => options?.onSseEvent?.({ data: undefined } as never), 60)
      return { stream: blockUntilAborted(options?.signal ?? undefined) }
    }) as unknown as typeof streamConsoleLiveApiLiveGet

    const stop = createConsoleLiveTransport({
      streamOperation: operation,
      idleTimeoutMs: 100,
      reconnectDelayMs: 0,
      sleep: async () => undefined,
    })

    await new Promise((resolve) => setTimeout(resolve, 130))
    expect(operation).toHaveBeenCalledTimes(1)
    stop()
  })

  it("surfaces malformed data without replacing the last valid projection", async () => {
    useConsoleLiveStore.getState().reset()
    useConsoleLiveStore.getState().applySnapshot(consoleSnapshot(7))
    const operation = vi.fn(async (options?: StreamOptions) => {
      options?.onSseEvent?.({ data: "not-json" } as never)
      return {
        stream: stream([
          "not-json" as unknown as StreamConsoleLiveApiLiveGetResponse,
        ]),
      }
    }) as unknown as typeof streamConsoleLiveApiLiveGet

    const stop = createConsoleLiveTransport({
      reconnectDelayMs: 0,
      streamOperation: operation,
      sleep: () => new Promise(() => undefined),
    })

    await vi.waitFor(() =>
      expect(useConsoleLiveStore.getState().connection.error).toMatch(
        /malformed/
      )
    )
    expect(useConsoleLiveStore.getState().can.frames_received).toBe(7)
    stop()
  })

  it("retains the last projection when generated validation rejects an event", async () => {
    useConsoleLiveStore.getState().reset()
    useConsoleLiveStore.getState().applySnapshot(consoleSnapshot(7))
    const operation = vi.fn(async (options?: StreamOptions) => {
      options?.onSseError?.(new Error("Invalid input: frames_received"))
      return { stream: blockUntilAborted(options?.signal ?? undefined) }
    }) as unknown as typeof streamConsoleLiveApiLiveGet

    const stop = createConsoleLiveTransport({
      streamOperation: operation,
      sleep: () => new Promise(() => undefined),
    })

    await vi.waitFor(() =>
      expect(useConsoleLiveStore.getState().connection.error).toMatch(
        /frames_received/
      )
    )
    expect(useConsoleLiveStore.getState().can.frames_received).toBe(7)
    stop()
  })
})
