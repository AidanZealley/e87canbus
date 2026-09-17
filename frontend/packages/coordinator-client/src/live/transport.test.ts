import { QueryClient } from "@tanstack/react-query"
import { describe, expect, it, vi } from "vitest"

import { streamCoordinatorLiveApiLiveGet } from "@e87canbus/coordinator-client/api/http/sdk.gen"
import type { StreamCoordinatorLiveApiLiveGetResponse } from "@e87canbus/coordinator-client/api/http/types.gen"
import { snapshot } from "./test-fixtures"
import { useLiveStore } from "./live-store"
import { createLiveTransport } from "./transport"

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

const stream = async function* (
  values: readonly StreamCoordinatorLiveApiLiveGetResponse[]
) {
  yield* values
}

const snapshotThenBlock = async function* (
  value: StreamCoordinatorLiveApiLiveGetResponse,
  signal?: AbortSignal
) {
  yield value
  yield* blockUntilAborted(signal)
}

const eventsThenBlock = async function* (
  values: readonly StreamCoordinatorLiveApiLiveGetResponse[],
  signal?: AbortSignal
) {
  yield* values
  yield* blockUntilAborted(signal)
}

describe("coordinator SSE transport", () => {
  it("applies generated events and reconciles durable roots after every snapshot", async () => {
    useLiveStore.getState().reset()
    const queryClient = new QueryClient()
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    const operation = vi.fn(async (options?: StreamOptions) => {
      options?.onSseError?.(new Error("read failed"))
      return {
        stream: eventsThenBlock(
          [
            snapshot(1),
            { type: "vehicle", data: { speed_kph: 42, speed_valid: true } },
            {
              type: "resource.changed",
              data: { resource: "settings", id: null, revision: 2 },
            },
          ],
          options?.signal ?? undefined
        ),
      }
    }) as unknown as typeof streamCoordinatorLiveApiLiveGet

    const stop = createLiveTransport({
      queryClient,
      streamOperation: operation,
      sleep: () => new Promise(() => undefined),
    })

    await vi.waitFor(() =>
      expect(useLiveStore.getState().vehicle.speed_kph).toBe(42)
    )
    expect(operation).toHaveBeenCalledTimes(1)
    expect(useLiveStore.getState().connection.error).toBeNull()
    await vi.waitFor(() => expect(invalidate).toHaveBeenCalledTimes(3))
    stop()
  })

  it("reconnects after clean EOF and starts again from a snapshot", async () => {
    useLiveStore.getState().reset()
    let calls = 0
    const operation = vi.fn(async (options?: StreamOptions) => {
      calls += 1
      return {
        stream:
          calls === 1
            ? stream([snapshot(1)])
            : snapshotThenBlock(snapshot(2), options?.signal ?? undefined),
      }
    }) as unknown as typeof streamCoordinatorLiveApiLiveGet

    const stop = createLiveTransport({
      queryClient: new QueryClient(),
      streamOperation: operation,
      reconnectDelayMs: 0,
      sleep: async () => undefined,
    })

    await vi.waitFor(() => expect(operation).toHaveBeenCalledTimes(2))
    await vi.waitFor(() =>
      expect(useLiveStore.getState().vehicle.speed_kph).toBe(2)
    )
    stop()
  })

  it("aborts an idle connection and reconnects", async () => {
    useLiveStore.getState().reset()
    let calls = 0
    const operation = vi.fn(async (options?: StreamOptions) => {
      calls += 1
      return {
        stream:
          calls === 1
            ? blockUntilAborted(options?.signal ?? undefined)
            : snapshotThenBlock(snapshot(2), options?.signal ?? undefined),
      }
    }) as unknown as typeof streamCoordinatorLiveApiLiveGet

    const stop = createLiveTransport({
      queryClient: new QueryClient(),
      streamOperation: operation,
      idleTimeoutMs: 100,
      reconnectDelayMs: 0,
      sleep: async () => undefined,
    })

    await vi.waitFor(() =>
      expect(useLiveStore.getState().connection.synchronized).toBe(true)
    )
    expect(operation).toHaveBeenCalledTimes(2)
    stop()
  })

  it("counts keepalive comments as receive activity", async () => {
    useLiveStore.getState().reset()
    const operation = vi.fn(async (options?: StreamOptions) => {
      setTimeout(() => options?.onSseEvent?.({ data: undefined } as never), 60)
      return { stream: blockUntilAborted(options?.signal ?? undefined) }
    }) as unknown as typeof streamCoordinatorLiveApiLiveGet

    const stop = createLiveTransport({
      queryClient: new QueryClient(),
      streamOperation: operation,
      idleTimeoutMs: 100,
      reconnectDelayMs: 0,
      sleep: async () => undefined,
    })

    await new Promise((resolve) => setTimeout(resolve, 130))
    expect(operation).toHaveBeenCalledTimes(1)
    stop()
  })

  it("surfaces malformed data without replacing the last valid projections", async () => {
    useLiveStore.getState().reset()
    useLiveStore.getState().applyEvent(snapshot(7))
    const operation = vi.fn(async (options?: StreamOptions) => {
      options?.onSseEvent?.({ data: "not-json" } as never)
      return {
        stream: stream([
          "not-json" as unknown as StreamCoordinatorLiveApiLiveGetResponse,
        ]),
      }
    }) as unknown as typeof streamCoordinatorLiveApiLiveGet

    const stop = createLiveTransport({
      queryClient: new QueryClient(),
      reconnectDelayMs: 0,
      streamOperation: operation,
      sleep: () => new Promise(() => undefined),
    })

    await vi.waitFor(() =>
      expect(useLiveStore.getState().connection.error).toMatch(/malformed/)
    )
    expect(useLiveStore.getState().vehicle.speed_kph).toBe(7)
    stop()
  })
})
