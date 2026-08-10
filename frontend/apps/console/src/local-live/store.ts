import { create } from "zustand"

import {
  CONSOLE_PROTOCOL_VERSION,
  type ConsoleCanState,
  type ConsoleSnapshotPayload,
} from "./contract.gen"

export type ConsoleConnectionStatus =
  | "connecting"
  | "synchronizing"
  | "connected"
  | "reconnecting"
  | "disconnected"
  | "incompatible"

type ConsoleLiveState = {
  bootId: string | null
  revision: number
  can: ConsoleCanState
  connection: {
    status: ConsoleConnectionStatus
    synchronized: boolean
    error: string | null
  }
  transportConnected: () => void
  transportDisconnected: () => void
  transportError: (message: string) => void
  applySnapshot: (snapshot: ConsoleSnapshotPayload) => boolean
  reset: () => void
}

const initialState = () => ({
  bootId: null,
  revision: 0,
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

export const useConsoleLiveStore = create<ConsoleLiveState>((set, get) => ({
  ...initialState(),
  transportConnected: () =>
    set((state) => ({
      connection: {
        status: state.bootId === null ? "synchronizing" : "reconnecting",
        synchronized: false,
        error: null,
      },
    })),
  transportDisconnected: () =>
    set((state) => ({
      connection: {
        status: state.bootId === null ? "connecting" : "reconnecting",
        synchronized: false,
        error: null,
      },
    })),
  transportError: (message) =>
    set({
      connection: {
        status: "disconnected",
        synchronized: false,
        error: message,
      },
    }),
  applySnapshot: (snapshot) => {
    if (snapshot.protocol_version !== CONSOLE_PROTOCOL_VERSION) {
      set({
        connection: {
          status: "incompatible",
          synchronized: false,
          error: `Console live protocol ${snapshot.protocol_version} is incompatible; this application requires version ${CONSOLE_PROTOCOL_VERSION}.`,
        },
      })
      return false
    }
    const current = get()
    if (
      current.bootId === snapshot.boot_id &&
      snapshot.revision <= current.revision
    ) {
      return false
    }
    set({
      bootId: snapshot.boot_id,
      revision: snapshot.revision,
      can: snapshot.data.can,
      connection: {
        status: "connected",
        synchronized: true,
        error: null,
      },
    })
    return true
  },
  reset: () => set(initialState()),
}))
