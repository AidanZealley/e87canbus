import type { QueryClient } from "@tanstack/react-query"
import { io, type Socket } from "socket.io-client"

import { API_BASE } from "@/api/client"
import {
  reconcileDurableResources,
  invalidateChangedResource,
} from "@/api/durable-query-ownership"
import type {
  ClientToServerEvents,
  ServerToClientEvents,
} from "@/api/live-events"
import { useLiveStore, type TopicApplyDecision } from "./live-store"
import { useTraceStore } from "./trace-store"

type LiveSocket = Socket<ServerToClientEvents, ClientToServerEvents>

type TransportDependencies = {
  queryClient: QueryClient
  createSocket?: () => LiveSocket
}

export const createLiveTransport = ({
  queryClient,
  createSocket = () =>
    io(API_BASE, {
      autoConnect: false,
      transports: ["websocket", "polling"],
    }) as LiveSocket,
}: TransportDependencies) => {
  let socket: LiveSocket | null = null
  let started = false
  let synchronizedOnce = false
  let connectionEpoch = 0
  let reconciledEpoch = -1
  let connectEventSeen = false
  let snapshotBeforeConnect = false
  let traceSubscribers = 0

  const requestResync = () => socket?.emit("controller.resync")
  const applyTopic = (decision: TopicApplyDecision) => {
    if (decision === "resync") requestResync()
  }
  const reconcileCurrentConnection = () => {
    if (reconciledEpoch === connectionEpoch) return
    reconciledEpoch = connectionEpoch
    void reconcileDurableResources(queryClient)
  }

  const listeners: {
    [Event in keyof ServerToClientEvents]: ServerToClientEvents[Event]
  } = {
    "controller.snapshot": (payload) => {
      if (!useLiveStore.getState().applySnapshot(payload)) return
      const trace = useTraceStore.getState()
      if (trace.bootId !== null && trace.bootId !== payload.boot_id)
        trace.clear()
      synchronizedOnce = true
      if (connectEventSeen) reconcileCurrentConnection()
      else snapshotBeforeConnect = true
    },
    "vehicle.state": (payload) =>
      applyTopic(useLiveStore.getState().applyVehicle(payload)),
    "engine.state": (payload) =>
      applyTopic(useLiveStore.getState().applyEngine(payload)),
    "steering.state": (payload) =>
      applyTopic(useLiveStore.getState().applySteering(payload)),
    "buttons.state": (payload) =>
      applyTopic(useLiveStore.getState().applyButtons(payload)),
    "devices.state": (payload) =>
      applyTopic(useLiveStore.getState().applyDevices(payload)),
    "controller.health": (payload) =>
      applyTopic(useLiveStore.getState().applyHealth(payload)),
    "resources.changed": (payload) => {
      void invalidateChangedResource(queryClient, payload)
    },
    "trace.batch": (payload) =>
      useTraceStore
        .getState()
        .applyBatch(payload, useLiveStore.getState().bootId),
  }

  const start = () => {
    if (started) return
    started = true
    socket = createSocket()
    socket.on("connect", () => {
      connectionEpoch += 1
      connectEventSeen = true
      if (traceSubscribers > 0) socket?.emit("trace.subscribe")
      if (snapshotBeforeConnect) {
        snapshotBeforeConnect = false
        reconcileCurrentConnection()
      } else {
        useLiveStore.getState().transportConnected(synchronizedOnce)
      }
    })
    socket.on("disconnect", () => {
      connectEventSeen = false
      snapshotBeforeConnect = false
      useTraceStore.getState().clear()
      useLiveStore.getState().transportDisconnected()
    })
    socket.on("connect_error", (error) => {
      useLiveStore.getState().transportError(error.message)
    })
    for (const [event, listener] of Object.entries(listeners)) {
      socket.on(event as keyof ServerToClientEvents, listener as never)
    }
    socket.connect()
  }

  const stop = () => {
    if (!started) return
    started = false
    if (traceSubscribers > 0) socket?.emit("trace.unsubscribe")
    traceSubscribers = 0
    socket?.removeAllListeners()
    socket?.disconnect()
    socket = null
    connectEventSeen = false
    snapshotBeforeConnect = false
    useTraceStore.getState().clear()
    useLiveStore.getState().reset()
  }

  const subscribeTrace = () => {
    traceSubscribers += 1
    if (traceSubscribers === 1 && socket?.connected) {
      socket.emit("trace.subscribe")
    }
    return () => {
      traceSubscribers = Math.max(0, traceSubscribers - 1)
      if (traceSubscribers === 0) {
        socket?.emit("trace.unsubscribe")
        useTraceStore.getState().clear()
      }
    }
  }

  return { start, stop, subscribeTrace }
}

export const createLiveTransportOwner = (
  createTransport: (
    queryClient: QueryClient
  ) => ReturnType<typeof createLiveTransport> = (queryClient) =>
    createLiveTransport({ queryClient })
) => {
  let singleton: ReturnType<typeof createLiveTransport> | null = null
  let owners = 0
  let traceOwners = 0
  let teardownGeneration = 0
  let releaseSingletonTrace: (() => void) | null = null

  const teardown = () => {
    teardownGeneration += 1
    owners = 0
    traceOwners = 0
    releaseSingletonTrace?.()
    releaseSingletonTrace = null
    singleton?.stop()
    singleton = null
  }

  const acquire = (queryClient: QueryClient) => {
    owners += 1
    teardownGeneration += 1
    if (singleton === null) singleton = createTransport(queryClient)
    singleton.start()
    if (traceOwners > 0 && releaseSingletonTrace === null) {
      releaseSingletonTrace = singleton.subscribeTrace()
    }
    let released = false
    return () => {
      if (released) return
      released = true
      owners = Math.max(0, owners - 1)
      if (owners !== 0) return
      const generation = ++teardownGeneration
      queueMicrotask(() => {
        if (owners === 0 && generation === teardownGeneration) teardown()
      })
    }
  }

  const subscribeTrace = () => {
    traceOwners += 1
    if (traceOwners === 1 && singleton !== null) {
      releaseSingletonTrace = singleton.subscribeTrace()
    }
    let released = false
    return () => {
      if (released) return
      released = true
      traceOwners = Math.max(0, traceOwners - 1)
      if (traceOwners === 0) {
        releaseSingletonTrace?.()
        releaseSingletonTrace = null
      }
    }
  }

  return { acquire, subscribeTrace, teardown }
}

const liveTransportOwner = createLiveTransportOwner()

export const startLiveTransport = (queryClient: QueryClient) =>
  liveTransportOwner.acquire(queryClient)

export const subscribeLiveTrace = () => liveTransportOwner.subscribeTrace()

export const teardownLiveTransport = () => liveTransportOwner.teardown()
