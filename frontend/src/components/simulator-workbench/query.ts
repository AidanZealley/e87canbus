import { useEffect, useState } from "react"
import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"

import { connectSimulatorSocket, getSnapshot } from "@/api/simulator"
import {
  applySimulatorEvent,
  setSimulatorSnapshot,
  simulatorQueryKey,
} from "./cache"
import type { SimulatorSnapshot } from "./types"
import { emptySnapshot, mergeSnapshot, type WorkbenchSnapshot } from "./utils"

const simulatorQueryOptions = queryOptions({
  queryKey: simulatorQueryKey,
  queryFn: async () => mergeSnapshot(emptySnapshot, await getSnapshot()),
  staleTime: Infinity,
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
const selectSteeringController = (snapshot: WorkbenchSnapshot) =>
  snapshot.steering_controller
const selectLedColours = (snapshot: WorkbenchSnapshot) => snapshot.led_colours
const selectNetworks = (snapshot: WorkbenchSnapshot) => snapshot.networks
const selectTrace = (snapshot: WorkbenchSnapshot) => snapshot.trace
const selectNothing = () => null

export const useApplicationSnapshot = () =>
  useSimulatorSelector(selectApplication)

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
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    if (!enabled) return

    let cancelled = false
    const socket = connectSimulatorSocket((event) => {
      if (!cancelled) applySimulatorEvent(queryClient, event)
    })

    socket.addEventListener("open", () => {
      if (cancelled) {
        socket.close()
        return
      }
      setConnected(true)
    })
    socket.addEventListener("close", () => {
      if (!cancelled) setConnected(false)
    })
    socket.addEventListener("error", () => {
      if (!cancelled) setConnected(false)
    })

    return () => {
      cancelled = true
      setConnected(false)
      if (socket.readyState === WebSocket.OPEN) socket.close()
    }
  }, [enabled, queryClient])

  return connected
}
