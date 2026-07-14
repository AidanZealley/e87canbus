export const RECONNECT_BASE_DELAY_MS = 500
export const RECONNECT_MAX_DELAY_MS = 10_000
export const INITIAL_CONNECT_RETRY_COUNT = 2
export const UNAVAILABLE_REFETCH_INTERVAL_MS = 10_000
export const HEARTBEAT_INTERVAL_MS = 5_000
export const HEARTBEAT_TIMEOUT_MS = 15_000

export type SimulatorConnectionState =
  "connecting" | "connected" | "disconnected" | "reconnecting"

export const reconnectDelay = (
  failureCount: number,
  random: () => number = Math.random
) => {
  const exponentialDelay = Math.min(
    RECONNECT_MAX_DELAY_MS,
    RECONNECT_BASE_DELAY_MS * 2 ** Math.max(0, failureCount)
  )
  return Math.round(exponentialDelay * (0.8 + random() * 0.4))
}
