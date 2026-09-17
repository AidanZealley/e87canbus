import type { QueryClient } from "@tanstack/react-query"
import { io, type Socket } from "socket.io-client"

import { COORDINATOR_ORIGIN } from "@e87canbus/coordinator-client/api/http-client-config"
import {
  reconcileDurableResources,
  invalidateChangedResource,
} from "@e87canbus/coordinator-client/api/durable-query-ownership"
import type {
  ClientToServerEvents,
  ServerToClientEvents,
} from "@e87canbus/coordinator-client/api/live-contract.gen"
import { useLiveStore, type TopicApplyDecision } from "./live-store"

type LiveSocket = Socket<ServerToClientEvents, ClientToServerEvents>
type RetainedServerEvent = Exclude<
  keyof ServerToClientEvents,
  "devices.state" | "trace.batch"
>

type TransportDependencies = {
  queryClient: QueryClient
  createSocket?: () => LiveSocket
}

export const createLiveTransport = ({
  queryClient,
  createSocket = () =>
    io(COORDINATOR_ORIGIN, {
      autoConnect: false,
      transports: ["websocket", "polling"],
    }) as LiveSocket,
}: TransportDependencies) => {
  const socket = createSocket()
  let synchronizedOnce = false
  let connectionEpoch = 0
  let reconciledEpoch = -1
  let connectEventSeen = false
  let snapshotBeforeConnect = false

  const requestResync = () => socket.emit("controller.resync")
  const applyTopic = (decision: TopicApplyDecision) => {
    if (decision === "resync") requestResync()
  }
  const reconcileCurrentConnection = () => {
    if (reconciledEpoch === connectionEpoch) return
    reconciledEpoch = connectionEpoch
    void reconcileDurableResources(queryClient)
  }

  const listeners: {
    [Event in RetainedServerEvent]: ServerToClientEvents[Event]
  } = {
    "controller.snapshot": (payload) => {
      if (!useLiveStore.getState().applySnapshot(payload)) return
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
    "lighting.state": (payload) =>
      applyTopic(useLiveStore.getState().applyLighting(payload)),
    "controller.health": (payload) =>
      applyTopic(useLiveStore.getState().applyHealth(payload)),
    "resources.changed": (payload) => {
      void invalidateChangedResource(queryClient, payload)
    },
  }

  socket.on("connect", () => {
    connectionEpoch += 1
    connectEventSeen = true
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

let liveTransportStarted = false

export const startLiveTransport = (queryClient: QueryClient) => {
  if (liveTransportStarted) return
  createLiveTransport({ queryClient })
  liveTransportStarted = true
}
