import { create } from "zustand"

import type { ConsoleCanState, ConsoleSnapshotData } from "@/api/console-host"

export type ConsoleConnectionStatus =
  "connecting" | "connected" | "reconnecting" | "disconnected"

type ConsoleLiveState = {
  can: ConsoleCanState
  connection: {
    status: ConsoleConnectionStatus
    synchronized: boolean
    error: string | null
  }
  connectionPending: () => void
  connectionFailed: (message: string) => void
  applySnapshot: (snapshot: ConsoleSnapshotData) => void
  reset: () => void
}

const initialState = () => ({
  can: {
    interface: "kcan" as const,
    connected: false,
    frames_received: 0,
    fault: null,
  },
  connection: {
    status: "connecting" as const,
    synchronized: false,
    error: null,
  },
})

export const useConsoleLiveStore = create<ConsoleLiveState>((set) => ({
  ...initialState(),
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
  applySnapshot: (snapshot) => {
    set({
      can: snapshot.can,
      connection: {
        status: "connected",
        synchronized: true,
        error: null,
      },
    })
  },
  reset: () => set(initialState()),
}))
