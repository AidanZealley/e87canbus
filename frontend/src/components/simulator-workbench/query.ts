import { useEffect, useState } from "react"
import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"

import { connectSimulatorSocket, getSnapshot } from "@/api/simulator"
import { steeringProfilesQueryKey } from "@/api/steering"
import {
  applySimulatorEvent,
  replaceSimulatorSnapshot,
  setSimulatorSnapshot,
  simulatorQueryKey,
} from "./cache"
import {
  HEARTBEAT_INTERVAL_MS,
  HEARTBEAT_TIMEOUT_MS,
  INITIAL_CONNECT_RETRY_COUNT,
  reconnectDelay,
  type SimulatorConnectionState,
  UNAVAILABLE_REFETCH_INTERVAL_MS,
} from "./connection"
import type { SimulatorSnapshot } from "./types"
import { emptySnapshot, mergeSnapshot, type WorkbenchSnapshot } from "./utils"

const simulatorQueryOptions = queryOptions({
  queryKey: simulatorQueryKey,
  queryFn: async () => mergeSnapshot(emptySnapshot, await getSnapshot()),
  staleTime: Infinity,
  retry: INITIAL_CONNECT_RETRY_COUNT,
  retryDelay: (failureCount) => reconnectDelay(failureCount),
  refetchInterval: (query) =>
    query.state.status === "error" ? UNAVAILABLE_REFETCH_INTERVAL_MS : false,
})

const useSimulatorSelector = <Selected>(
  select: (snapshot: WorkbenchSnapshot) => Selected
) => {
  const query = useQuery({
    ...simulatorQueryOptions,
    placeholderData: emptySnapshot,
    select,
  })
  return query.data ?? select(emptySnapshot)
}

const selectApplication = (snapshot: WorkbenchSnapshot) => snapshot.application
const selectActiveSteeringCurve = (snapshot: WorkbenchSnapshot) =>
  snapshot.application.active_steering_curve
const selectSteeringController = (snapshot: WorkbenchSnapshot) =>
  snapshot.steering_controller
const selectLedColours = (snapshot: WorkbenchSnapshot) => snapshot.led_colours
const selectNetworks = (snapshot: WorkbenchSnapshot) => snapshot.networks
const selectTrace = (snapshot: WorkbenchSnapshot) => snapshot.trace
const selectNothing = () => null

export const useApplicationSnapshot = () =>
  useSimulatorSelector(selectApplication)

export const useActiveSteeringCurve = () =>
  useSimulatorSelector(selectActiveSteeringCurve)

export const useSteeringControllerSnapshot = () =>
  useSimulatorSelector(selectSteeringController)

export const useLedColours = () => useSimulatorSelector(selectLedColours)

export const useNetworks = () => useSimulatorSelector(selectNetworks)

export const useTrace = () => useSimulatorSelector(selectTrace)

export const useSimulatorStatus = () =>
  useQuery({
    ...simulatorQueryOptions,
    placeholderData: emptySnapshot,
    select: selectNothing,
  })

export type SimulatorCommand = () => Promise<SimulatorSnapshot>

export const useSimulatorCommand = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (command: SimulatorCommand) => command(),
    onSuccess: (snapshot) => setSimulatorSnapshot(queryClient, snapshot),
  })
}

export const useSimulatorSocket = (enabled: boolean) => {
  const queryClient = useQueryClient()
  const [connectionState, setConnectionState] =
    useState<SimulatorConnectionState>("connecting")

  useEffect(() => {
    if (!enabled) return

    let cancelled = false
    let socket: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined
    let heartbeatTimer: ReturnType<typeof setInterval> | undefined
    let reconnectAttempt = 0
    let hasConnected = false
    let awaitingInitialSnapshot = true
    let lastMessageAt = 0

    const stopHeartbeat = () => {
      if (heartbeatTimer !== undefined) clearInterval(heartbeatTimer)
      heartbeatTimer = undefined
    }

    const closeSocket = () => {
      if (
        socket?.readyState === WebSocket.CONNECTING ||
        socket?.readyState === WebSocket.OPEN
      ) {
        socket.close()
      }
    }

    const connect = () => {
      if (cancelled) return

      awaitingInitialSnapshot = true
      lastMessageAt = Date.now()
      setConnectionState(hasConnected ? "reconnecting" : "connecting")

      const activeSocket = connectSimulatorSocket(
        (event) => {
          if (cancelled || socket !== activeSocket) return
          lastMessageAt = Date.now()
          if (event.type === "steering_profile_catalog_changed") {
            void queryClient.invalidateQueries({
              queryKey: steeringProfilesQueryKey,
            })
            return
          }
          if (awaitingInitialSnapshot) {
            if (event.type !== "snapshot") return
            replaceSimulatorSnapshot(queryClient, event.snapshot)
            awaitingInitialSnapshot = false
            reconnectAttempt = 0
            hasConnected = true
            setConnectionState("connected")
            return
          }
          applySimulatorEvent(queryClient, event)
        },
        () => {
          if (!cancelled && socket === activeSocket) {
            lastMessageAt = Date.now()
          }
        }
      )
      socket = activeSocket

      activeSocket.addEventListener("open", () => {
        if (cancelled || socket !== activeSocket) {
          activeSocket.close()
          return
        }
        lastMessageAt = Date.now()
        heartbeatTimer = setInterval(() => {
          if (activeSocket.readyState !== WebSocket.OPEN) return
          if (Date.now() - lastMessageAt >= HEARTBEAT_TIMEOUT_MS) {
            activeSocket.close(4000, "heartbeat timeout")
            return
          }
          activeSocket.send("ping")
        }, HEARTBEAT_INTERVAL_MS)
      })

      activeSocket.addEventListener("close", () => {
        if (cancelled || socket !== activeSocket) return
        stopHeartbeat()
        socket = null
        setConnectionState(hasConnected ? "reconnecting" : "connecting")
        reconnectTimer = setTimeout(connect, reconnectDelay(reconnectAttempt))
        reconnectAttempt += 1
      })

      activeSocket.addEventListener("error", () => {
        if (!cancelled && socket === activeSocket) {
          setConnectionState(hasConnected ? "reconnecting" : "connecting")
        }
      })
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer !== undefined) clearTimeout(reconnectTimer)
      stopHeartbeat()
      closeSocket()
    }
  }, [enabled, queryClient])

  return connectionState
}
