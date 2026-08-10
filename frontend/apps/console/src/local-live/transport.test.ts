import { beforeEach, expect, it } from "vitest"

import { consoleSnapshot } from "./test-fixtures"
import { useConsoleLiveStore } from "./store"
import { consoleSocketOptions, createConsoleLiveTransport } from "./transport"

class FakeSocket {
  handlers = new Map<string, Set<(payload?: unknown) => void>>()
  connects = 0

  on(event: string, listener: (payload?: unknown) => void) {
    const listeners = this.handlers.get(event) ?? new Set()
    listeners.add(listener)
    this.handlers.set(event, listeners)
    return this
  }

  connect() {
    this.connects += 1
    return this
  }

  fire(event: string, payload?: unknown) {
    for (const listener of this.handlers.get(event) ?? []) listener(payload)
  }
}

beforeEach(() => useConsoleLiveStore.getState().reset())

it("uses the console-only Socket.IO path", () => {
  expect(consoleSocketOptions).toEqual({
    autoConnect: false,
    path: "/console/socket.io",
    transports: ["websocket", "polling"],
  })
})

it("owns one local connection and applies the first complete snapshot", () => {
  const socket = new FakeSocket()
  createConsoleLiveTransport(() => socket as never)

  expect(socket.connects).toBe(1)
  expect(socket.handlers.get("console.snapshot")?.size).toBe(1)
  socket.fire("connect")
  expect(useConsoleLiveStore.getState().connection.status).toBe("synchronizing")
  socket.fire("console.snapshot", consoleSnapshot("console-boot", 1, 7))
  expect(useConsoleLiveStore.getState()).toMatchObject({
    bootId: "console-boot",
    can: { frames_received: 7 },
    connection: { status: "connected", synchronized: true },
  })
  socket.fire("disconnect")
  expect(useConsoleLiveStore.getState().connection.status).toBe("reconnecting")
})

it("stays synchronized when the server snapshot arrives before connect", () => {
  const socket = new FakeSocket()
  createConsoleLiveTransport(() => socket as never)

  socket.fire("console.snapshot", consoleSnapshot("early-boot", 1, 3))
  socket.fire("connect")

  expect(useConsoleLiveStore.getState()).toMatchObject({
    bootId: "early-boot",
    can: { frames_received: 3 },
    connection: { status: "connected", synchronized: true },
  })
})
