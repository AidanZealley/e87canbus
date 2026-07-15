import { create } from "zustand"

import {
  LIVE_PROTOCOL_VERSION,
  type ButtonsState,
  type ControllerHealthState,
  type ControllerSnapshotData,
  type DevicesState,
  type EngineState,
  type LiveEnvelope,
  type SteeringState,
  type TopicName,
  type TopicRevisions,
  type VehicleState,
} from "@/api/live-events"

export type LiveConnectionStatus =
  | "connecting"
  | "synchronizing"
  | "connected"
  | "reconnecting"
  | "disconnected"
  | "incompatible"

export type TopicApplyDecision =
  "applied" | "ignored" | "resync" | "incompatible"

type LiveConnection = {
  status: LiveConnectionStatus
  synchronized: boolean
  error: string | null
}

type LiveSlices = {
  bootId: string | null
  topicRevisions: TopicRevisions
  simulationSessionId: number | null
  vehicle: VehicleState
  engine: EngineState
  steering: SteeringState | null
  buttons: ButtonsState
  devices: DevicesState
  health: ControllerHealthState
}

export type LiveState = LiveSlices & {
  connection: LiveConnection
  transportConnected: (reconnecting: boolean) => void
  transportDisconnected: () => void
  transportError: (message: string) => void
  applySnapshot: (envelope: LiveEnvelope<ControllerSnapshotData>) => boolean
  applyVehicle: (envelope: LiveEnvelope<VehicleState>) => TopicApplyDecision
  applyEngine: (envelope: LiveEnvelope<EngineState>) => TopicApplyDecision
  applySteering: (envelope: LiveEnvelope<SteeringState>) => TopicApplyDecision
  applyButtons: (envelope: LiveEnvelope<ButtonsState>) => TopicApplyDecision
  applyDevices: (envelope: LiveEnvelope<DevicesState>) => TopicApplyDecision
  applyHealth: (
    envelope: LiveEnvelope<ControllerHealthState>
  ) => TopicApplyDecision
  reset: () => void
}

const zeroRevisions = (): TopicRevisions => ({
  vehicle: 0,
  engine: 0,
  steering: 0,
  buttons: 0,
  devices: 0,
  health: 0,
})

const emptySlices = (): LiveSlices => ({
  bootId: null,
  topicRevisions: zeroRevisions(),
  simulationSessionId: null,
  vehicle: { speed_kph: 0, speed_valid: false },
  engine: {
    rpm: { value: null, status: "never_observed" },
    oil_temperature_c: { value: null, status: "never_observed" },
    coolant_temperature_c: { value: null, status: "never_observed" },
  },
  steering: null,
  buttons: { led_colours: Array<number>(16).fill(0), next_pressed: null },
  devices: { devices: [], networks: [], steering_controller: null },
  health: {
    lifecycle: "created",
    fatal: false,
    networks: [],
    steering_actuator_fault: null,
  },
})

const initialConnection = (): LiveConnection => ({
  status: "connecting",
  synchronized: false,
  error: null,
})

const incompatibleMessage = (version: number) =>
  `Live protocol ${version} is incompatible; this application requires version ${LIVE_PROTOCOL_VERSION}.`

export const useLiveStore = create<LiveState>((set, get) => {
  const applyTopic = <Topic extends TopicName, Value>(
    topic: Topic,
    field: Topic,
    envelope: LiveEnvelope<Value>
  ): TopicApplyDecision => {
    const current = get()
    if (envelope.protocol_version !== LIVE_PROTOCOL_VERSION) {
      set({
        connection: {
          status: "incompatible",
          synchronized: false,
          error: incompatibleMessage(envelope.protocol_version),
        },
      })
      return "incompatible"
    }
    if (current.bootId !== envelope.boot_id) return "resync"
    if (envelope.revision <= current.topicRevisions[topic]) return "ignored"
    set({
      [field]: envelope.data,
      topicRevisions: {
        ...current.topicRevisions,
        [topic]: envelope.revision,
      },
    } as Partial<LiveState>)
    return "applied"
  }

  return {
    ...emptySlices(),
    connection: initialConnection(),
    transportConnected: (reconnecting) =>
      set({
        connection: {
          status: reconnecting ? "reconnecting" : "synchronizing",
          synchronized: false,
          error: null,
        },
      }),
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
    applySnapshot: (envelope) => {
      if (envelope.protocol_version !== LIVE_PROTOCOL_VERSION) {
        set({
          connection: {
            status: "incompatible",
            synchronized: false,
            error: incompatibleMessage(envelope.protocol_version),
          },
        })
        return false
      }
      const current = get()
      const sameBoot = current.bootId === envelope.boot_id
      if (
        sameBoot &&
        Object.entries(envelope.data.topic_revisions).some(
          ([topic, revision]) =>
            revision < current.topicRevisions[topic as TopicName]
        )
      ) {
        return false
      }
      set({
        bootId: envelope.boot_id,
        topicRevisions: { ...envelope.data.topic_revisions },
        simulationSessionId: envelope.data.simulation_session_id,
        vehicle: envelope.data.vehicle,
        engine: envelope.data.engine,
        steering: envelope.data.steering,
        buttons: envelope.data.buttons,
        devices: envelope.data.devices,
        health: envelope.data.health,
        connection: {
          status: "connected",
          synchronized: true,
          error: null,
        },
      })
      return true
    },
    applyVehicle: (envelope) => applyTopic("vehicle", "vehicle", envelope),
    applyEngine: (envelope) => applyTopic("engine", "engine", envelope),
    applySteering: (envelope) => applyTopic("steering", "steering", envelope),
    applyButtons: (envelope) => applyTopic("buttons", "buttons", envelope),
    applyDevices: (envelope) => applyTopic("devices", "devices", envelope),
    applyHealth: (envelope) => applyTopic("health", "health", envelope),
    reset: () => set({ ...emptySlices(), connection: initialConnection() }),
  }
})
