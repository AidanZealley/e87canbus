import type { QueryClient } from "@tanstack/react-query"

import type { SimulatorEvent, SimulatorSnapshot } from "./types.ts"
import {
  emptySnapshot,
  mergeSnapshot,
  reduceSimulatorEvent,
  type WorkbenchSnapshot,
} from "./utils.ts"

export const simulatorQueryKey = ["simulator"] as const

export const setSimulatorSnapshot = (
  queryClient: QueryClient,
  snapshot: SimulatorSnapshot
) => {
  queryClient.setQueryData<WorkbenchSnapshot>(simulatorQueryKey, (current) =>
    mergeSnapshot(current ?? emptySnapshot, snapshot)
  )
}

export const replaceSimulatorSnapshot = (
  queryClient: QueryClient,
  snapshot: SimulatorSnapshot
) => {
  queryClient.setQueryData<WorkbenchSnapshot>(
    simulatorQueryKey,
    mergeSnapshot(emptySnapshot, snapshot)
  )
}

export const applySimulatorEvent = (
  queryClient: QueryClient,
  event: SimulatorEvent
) => {
  queryClient.setQueryData<WorkbenchSnapshot>(simulatorQueryKey, (current) =>
    reduceSimulatorEvent(current ?? emptySnapshot, event)
  )
}
