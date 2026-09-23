import { create } from "zustand"

import type {
  ButtonsState,
  CoordinatorHealthState,
  EngineState,
  SnapshotEvent,
  SteeringState,
  StreamCoordinatorLiveApiLiveGetResponse,
  VehicleState,
} from "@e87canbus/coordinator-client/api/http/types.gen"

export type LiveConnectionStatus =
  "connecting" | "connected" | "reconnecting" | "disconnected"

type LiveConnection = {
  status: LiveConnectionStatus
  synchronized: boolean
  error: string | null
}

type LiveProjections = {
  vehicle: VehicleState
  engine: EngineState
  steering: SteeringState | null
  buttons: ButtonsState
  health: CoordinatorHealthState
}

export type LiveState = LiveProjections & {
  connection: LiveConnection
  connectionPending: () => void
  connectionFailed: (message: string) => void
  applyEvent: (event: StreamCoordinatorLiveApiLiveGetResponse) => void
  reset: () => void
}

const emptyProjections = (): LiveProjections => ({
  vehicle: { speed_kph: 0, speed_valid: false },
  engine: {
    rpm: { value: null, status: "never_observed" },
    oil_temperature_c: { value: null, status: "never_observed" },
    coolant_temperature_c: { value: null, status: "never_observed" },
  },
  steering: null,
  buttons: {
    active_profile_id: "built-in",
    active_profile_revision: null,
  },
  health: {
    ready: false,
    fatal: false,
    networks: [],
    inbox: {
      depth: 0,
      capacity: 1,
      current_latency_s: 0,
      latency_warning: false,
      overflow_latched: false,
    },
    persistence: { available: false, fault: "not initialized" },
  },
})

const initialConnection = (): LiveConnection => ({
  status: "connecting",
  synchronized: false,
  error: null,
})

export const useLiveStore = create<LiveState>((set, get) => {
  const applySnapshot = (event: SnapshotEvent) => {
    set({
      ...event.data,
      connection: {
        status: "connected",
        synchronized: true,
        error: null,
      },
    })
  }

  return {
    ...emptyProjections(),
    connection: initialConnection(),
    connectionPending: () =>
      set((state) => ({
        connection: {
          status:
            state.connection.status === "connecting"
              ? "connecting"
              : "reconnecting",
          synchronized: false,
          error: state.connection.error,
        },
      })),
    connectionFailed: (message) =>
      set({
        connection: {
          status: "disconnected",
          synchronized: false,
          error: message,
        },
      }),
    applyEvent: (event) => {
      if (event.type === "snapshot") {
        applySnapshot(event)
        return
      }
      if (event.type === "resource.changed" || !get().connection.synchronized)
        return
      switch (event.type) {
        case "vehicle":
          set({ vehicle: event.data })
          return
        case "engine":
          set({ engine: event.data })
          return
        case "steering":
          set({ steering: event.data })
          return
        case "buttons":
          set({ buttons: event.data })
          return
        case "health":
          set({ health: event.data })
          return
      }
      const unhandledEvent: never = event
      return unhandledEvent
    },
    reset: () =>
      set({ ...emptyProjections(), connection: initialConnection() }),
  }
})
