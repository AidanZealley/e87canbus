import { streamConsoleLiveApiLiveGet } from "@/api/console-host"
import { useConsoleLiveStore } from "./store"

const IDLE_TIMEOUT_MS = 25_000
const RECONNECT_DELAY_MS = 3_000

type StreamOperation = typeof streamConsoleLiveApiLiveGet

type TransportDependencies = {
  streamOperation?: StreamOperation
  idleTimeoutMs?: number
  reconnectDelayMs?: number
  sleep?: (milliseconds: number) => Promise<void>
}

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "Console live stream failed"

export const createConsoleLiveTransport = ({
  streamOperation = streamConsoleLiveApiLiveGet,
  idleTimeoutMs = IDLE_TIMEOUT_MS,
  reconnectDelayMs = RECONNECT_DELAY_MS,
  sleep = (milliseconds) =>
    new Promise((resolve) => window.setTimeout(resolve, milliseconds)),
}: TransportDependencies = {}) => {
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

      const resetIdleTimer = () => {
        clearTimeout(idleTimer)
        idleTimer = setTimeout(() => {
          idleTimedOut = true
          useConsoleLiveStore
            .getState()
            .connectionFailed("Console live stream timed out")
          connectionAbort.abort()
        }, idleTimeoutMs)
      }

      try {
        resetIdleTimer()
        const { stream } = await streamOperation({
          signal: connectionAbort.signal,
          onSseEvent: (event) => {
            resetIdleTimer()
            if (event.data === undefined) return
            if (typeof event.data === "object" && event.data !== null) return
            malformedRecord = true
            useConsoleLiveStore
              .getState()
              .connectionFailed("Console sent malformed live data")
            connectionAbort.abort()
          },
          onSseError: (error) => {
            if (
              idleTimedOut ||
              malformedRecord ||
              transportAbort.signal.aborted
            )
              return
            useConsoleLiveStore.getState().connectionFailed(errorMessage(error))
          },
        })

        for await (const event of stream) {
          if (!malformedRecord)
            useConsoleLiveStore.getState().applySnapshot(event.data)
        }

        if (!transportAbort.signal.aborted && !idleTimedOut && !malformedRecord)
          useConsoleLiveStore
            .getState()
            .connectionFailed("Console live stream ended")
      } catch (error) {
        if (!transportAbort.signal.aborted && !idleTimedOut && !malformedRecord)
          useConsoleLiveStore.getState().connectionFailed(errorMessage(error))
      } finally {
        clearTimeout(idleTimer)
        connectionAbort.abort()
        transportAbort.signal.removeEventListener("abort", stopTransport)
      }

      if (transportAbort.signal.aborted) return
      await sleep(reconnectDelayMs)
      if (!transportAbort.signal.aborted)
        useConsoleLiveStore.getState().connectionPending()
    }
  }

  void run()
  return () => transportAbort.abort()
}

let activeConsoleLiveTransport: (() => void) | null = null

export const startConsoleLiveTransport = () => {
  if (activeConsoleLiveTransport !== null) return
  activeConsoleLiveTransport = createConsoleLiveTransport()
}

export const disposeConsoleLiveTransport = () => {
  activeConsoleLiveTransport?.()
  activeConsoleLiveTransport = null
}

if (import.meta.hot) import.meta.hot.dispose(disposeConsoleLiveTransport)
