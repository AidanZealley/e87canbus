import {
  io,
  type ManagerOptions,
  type Socket,
  type SocketOptions,
} from "socket.io-client"

import type { ConsoleServerEvents } from "./contract.gen"
import { CONSOLE_SOCKET_PATH } from "./config"
import { useConsoleLiveStore } from "./store"

type ConsoleSocket = Socket<ConsoleServerEvents, Record<string, never>>

export const consoleSocketOptions = {
  autoConnect: false,
  path: CONSOLE_SOCKET_PATH,
  transports: ["websocket", "polling"],
} satisfies Partial<ManagerOptions & SocketOptions>

export const createConsoleLiveTransport = (
  createSocket: () => ConsoleSocket = () =>
    io(consoleSocketOptions) as ConsoleSocket
) => {
  const socket = createSocket()
  socket.on("connect", () => {
    const state = useConsoleLiveStore.getState()
    if (!state.connection.synchronized) state.transportConnected()
  })
  socket.on("disconnect", () => {
    useConsoleLiveStore.getState().transportDisconnected()
  })
  socket.on("connect_error", (error) => {
    useConsoleLiveStore.getState().transportError(error.message)
  })
  socket.on("console.snapshot", (snapshot) => {
    useConsoleLiveStore.getState().applySnapshot(snapshot)
  })
  socket.connect()
  return socket
}

let consoleLiveSocket: ConsoleSocket | null = null

export const startConsoleLiveTransport = () => {
  consoleLiveSocket ??= createConsoleLiveTransport()
}
