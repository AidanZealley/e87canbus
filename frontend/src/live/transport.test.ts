import { QueryClient } from "@tanstack/react-query"
import { describe, expect, it, vi } from "vitest"

import { createLiveTransport, createLiveTransportOwner } from "./transport"
import { useLiveStore } from "./live-store"
import { snapshot } from "./test-fixtures"

class FakeSocket {
  handlers = new Map<string, Set<(...args: never[]) => void>>()
  emitted: string[] = []
  connects = 0
  disconnects = 0
  on(event: string, listener: (...args: never[]) => void) {
    const handlers = this.handlers.get(event) ?? new Set()
    handlers.add(listener)
    this.handlers.set(event, handlers)
    return this
  }
  emit(event: string) {
    this.emitted.push(event)
    return this
  }
  connect() {
    this.connects += 1
    return this
  }
  disconnect() {
    this.disconnects += 1
    return this
  }
  removeAllListeners() {
    this.handlers.clear()
    return this
  }
  fire(event: string, payload?: unknown) {
    for (const handler of this.handlers.get(event) ?? [])
      handler(payload as never)
  }
}

describe("Socket.IO transport owner", () => {
  it("owns one connection/listener set, synchronizes on snapshot, and tears down fully", async () => {
    useLiveStore.getState().reset()
    const socket = new FakeSocket()
    const queryClient = new QueryClient()
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    const transport = createLiveTransport({
      queryClient,
      createSocket: () => socket as never,
    })
    transport.start()
    transport.start()
    expect(socket.connects).toBe(1)
    for (const event of [
      "controller.snapshot",
      "vehicle.state",
      "engine.state",
      "steering.state",
      "buttons.state",
      "devices.state",
      "controller.health",
      "resources.changed",
      "trace.batch",
    ]) {
      expect(socket.handlers.get(event)?.size).toBe(1)
    }
    socket.fire("connect")
    expect(useLiveStore.getState().connection.status).toBe("synchronizing")
    socket.fire("controller.snapshot", snapshot("transport-boot", 1))
    expect(useLiveStore.getState().connection.status).toBe("connected")
    await vi.waitFor(() => expect(invalidate).toHaveBeenCalledTimes(2))
    socket.fire("controller.snapshot", snapshot("transport-boot", 1))
    await Promise.resolve()
    expect(invalidate).toHaveBeenCalledTimes(2)
    socket.fire("disconnect")
    expect(useLiveStore.getState().connection.synchronized).toBe(false)
    socket.fire("connect")
    socket.fire("controller.snapshot", snapshot("transport-boot", 1))
    await vi.waitFor(() => expect(invalidate).toHaveBeenCalledTimes(4))
    socket.fire("resources.changed", {
      type: "resources.changed",
      resource: "settings",
      id: null,
      revision: 2,
    })
    await vi.waitFor(() => expect(invalidate).toHaveBeenCalledTimes(5))
    const releaseTrace = transport.subscribeTrace()
    releaseTrace()
    expect(socket.emitted).toEqual(["trace.subscribe", "trace.unsubscribe"])
    transport.stop()
    expect(socket.disconnects).toBe(1)
    expect(socket.handlers.size).toBe(0)
  })

  it("requests resync instead of accepting a topic from another boot", () => {
    const socket = new FakeSocket()
    const transport = createLiveTransport({
      queryClient: new QueryClient(),
      createSocket: () => socket as never,
    })
    transport.start()
    socket.fire("controller.snapshot", snapshot("boot-a", 1))
    socket.fire("vehicle.state", {
      ...snapshot("boot-a", 1),
      data: { speed_kph: 10, speed_valid: true },
    })
    expect(socket.emitted).not.toContain("controller.resync")
    socket.fire("vehicle.state", {
      ...snapshot("boot-b", 2),
      data: { speed_kph: 99, speed_valid: true },
    })
    expect(socket.emitted).toContain("controller.resync")
    expect(useLiveStore.getState().bootId).toBe("boot-a")
    transport.stop()
  })

  it("stays synchronized when the server snapshot arrives before the local connect event", async () => {
    useLiveStore.getState().reset()
    const socket = new FakeSocket()
    const queryClient = new QueryClient()
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    const transport = createLiveTransport({
      queryClient,
      createSocket: () => socket as never,
    })
    transport.start()
    socket.fire("controller.snapshot", snapshot("early-snapshot", 1))
    expect(useLiveStore.getState().connection.status).toBe("connected")
    expect(invalidate).not.toHaveBeenCalled()
    socket.fire("connect")
    expect(useLiveStore.getState().connection).toMatchObject({
      status: "connected",
      synchronized: true,
    })
    await vi.waitFor(() => expect(invalidate).toHaveBeenCalledTimes(2))
    socket.fire("controller.snapshot", snapshot("early-snapshot", 1))
    await Promise.resolve()
    expect(invalidate).toHaveBeenCalledTimes(2)
    transport.stop()
  })

  it("retains one client and listener set across the Strict Mode cleanup and setup cycle", async () => {
    const socket = new FakeSocket()
    const factory = vi.fn((queryClient: QueryClient) =>
      createLiveTransport({ queryClient, createSocket: () => socket as never })
    )
    const owner = createLiveTransportOwner(factory)
    const queryClient = new QueryClient()
    const releaseFirstMount = owner.acquire(queryClient)
    releaseFirstMount()
    const releaseStrictRemount = owner.acquire(queryClient)
    await Promise.resolve()
    expect(factory).toHaveBeenCalledOnce()
    expect(socket.connects).toBe(1)
    expect(socket.handlers.get("controller.snapshot")?.size).toBe(1)
    expect(socket.disconnects).toBe(0)
    releaseStrictRemount()
    await Promise.resolve()
    expect(socket.disconnects).toBe(1)
    expect(socket.handlers.size).toBe(0)
  })
})
