import type { QueryClient } from "@tanstack/react-query"

import {
  invalidateChangedResource,
  reconcileDurableResources,
} from "@e87canbus/coordinator-client/api/durable-query-ownership"
import { streamCoordinatorLiveApiLiveGet } from "@e87canbus/coordinator-client/api/http/sdk.gen"
import { useLiveStore } from "./live-store"

const IDLE_TIMEOUT_MS = 25_000
const RECONNECT_DELAY_MS = 3_000

type StreamOperation = typeof streamCoordinatorLiveApiLiveGet

type TransportDependencies = {
  queryClient: QueryClient
  streamOperation?: StreamOperation
  idleTimeoutMs?: number
  reconnectDelayMs?: number
  sleep?: (milliseconds: number) => Promise<void>
}

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "Coordinator live stream failed"

export const createLiveTransport = ({
  queryClient,
  streamOperation = streamCoordinatorLiveApiLiveGet,
  idleTimeoutMs = IDLE_TIMEOUT_MS,
  reconnectDelayMs = RECONNECT_DELAY_MS,
  sleep = (milliseconds) =>
    new Promise((resolve) => window.setTimeout(resolve, milliseconds)),
}: TransportDependencies) => {
  const transportAbort = new AbortController()

  const run = async () => {
    while (!transportAbort.signal.aborted) {
      const connectionAbort = new AbortController()
      const stopTransport = () => connectionAbort.abort()
      transportAbort.signal.addEventListener("abort", stopTransport, {
        once: true,
      })
      let idleTimer: ReturnType<typeof setTimeout> | undefined
      let idleTimedOut = false
      let malformedRecord = false
      let streamFailed = false

      const resetIdleTimer = () => {
        clearTimeout(idleTimer)
        idleTimer = setTimeout(() => {
          idleTimedOut = true
          useLiveStore
            .getState()
            .connectionFailed("Coordinator live stream timed out")
          connectionAbort.abort()
        }, idleTimeoutMs)
      }

      try {
        resetIdleTimer()
        const { stream } = await streamOperation({
          signal: connectionAbort.signal,
          sseMaxRetryAttempts: 1,
          onSseEvent: (event) => {
            resetIdleTimer()
            if (event.data === undefined) return
            if (typeof event.data === "object" && event.data !== null) return
            malformedRecord = true
            useLiveStore
              .getState()
              .connectionFailed("Coordinator sent malformed live data")
            connectionAbort.abort()
          },
          onSseError: (error) => {
            if (
              idleTimedOut ||
              malformedRecord ||
              transportAbort.signal.aborted
            )
              return
            streamFailed = true
            useLiveStore.getState().connectionFailed(errorMessage(error))
          },
        })

        for await (const value of stream) {
          if (malformedRecord) continue
          if (value.type === "resource.changed") {
            void invalidateChangedResource(queryClient, value.data)
            continue
          }
          useLiveStore.getState().applyEvent(value)
          if (value.type === "snapshot")
            void reconcileDurableResources(queryClient)
        }

        if (
          !transportAbort.signal.aborted &&
          !idleTimedOut &&
          !malformedRecord &&
          !streamFailed
        )
          useLiveStore
            .getState()
            .connectionFailed("Coordinator live stream ended")
      } catch (error) {
        if (!transportAbort.signal.aborted && !idleTimedOut && !malformedRecord)
          useLiveStore.getState().connectionFailed(errorMessage(error))
      } finally {
        clearTimeout(idleTimer)
        connectionAbort.abort()
        transportAbort.signal.removeEventListener("abort", stopTransport)
      }

      if (transportAbort.signal.aborted) return
      await sleep(reconnectDelayMs)
      if (!transportAbort.signal.aborted)
        useLiveStore.getState().connectionPending()
    }
  }

  void run()
  return () => transportAbort.abort()
}

let activeLiveTransport: (() => void) | null = null

export const startLiveTransport = (queryClient: QueryClient) => {
  if (activeLiveTransport !== null) return
  activeLiveTransport = createLiveTransport({ queryClient })
}

export const disposeLiveTransport = () => {
  activeLiveTransport?.()
  activeLiveTransport = null
}

if (import.meta.hot) import.meta.hot.dispose(disposeLiveTransport)
