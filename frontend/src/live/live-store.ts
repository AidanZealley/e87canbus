import { create } from "zustand"

import {
  LIVE_PROTOCOL_VERSION,
  type ButtonsState,
  type ControllerHealthState,
  type ControllerSnapshotData,
  type DevicesState,
  type EngineState,
  type LightingState,
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
  lighting: LightingState
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
  applyLighting: (envelope: LiveEnvelope<LightingState>) => TopicApplyDecision
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
  lighting: 0,
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
  buttons: { led_rgb: Array.from({ length: 16 }, () => [0, 0, 0] as [number, number, number]) },
  lighting: {
    high_beam_enabled: false,
    high_beam_strobe_active: false,
    high_beam_strobe_cycles_remaining: 0,
    observed_high_beam_enabled: null,
  },
  devices: {
    registry: {
      button_pad: {
        role: "button_pad",
        label: "Button pad",
        device_id: 1,
        source_mode: "disabled",
        status: "disabled",
        protocol_version: null,
        device_session_id: null,
        last_status_code: null,
        last_transition_monotonic_s: null,
      },
      servotronic_controller: {
        role: "servotronic_controller",
        label: "Servotronic controller",
        device_id: 1,
        source_mode: "disabled",
        status: "disabled",
        protocol_version: null,
        device_session_id: null,
        last_status_code: null,
        last_transition_monotonic_s: null,
      },
    },
    networks: [],
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
    devices: [],
    steering: {
      fault: null,
    },
    persistence: { available: false, fault: "not initialized" },
    publisher: {
      running: false,
      failures: 0,
      trace_rows_dropped: 0,
      resource_changes_dropped: 0,
      transport_queue_saturations: 0,
      fault: "not started",
    },
  },
})

const initialConnection = (): LiveConnection => ({
  status: "connecting",
  synchronized: false,
  error: null,
})

const incompatibleMessage = (version: number) =>
  `Live protocol ${version} is incompatible; this application requires version ${LIVE_PROTOCOL_VERSION}.`

const registryEntryEqual = (
  left: DevicesState["registry"][keyof DevicesState["registry"]],
  right: DevicesState["registry"][keyof DevicesState["registry"]]
) =>
  left.role === right.role &&
  left.label === right.label &&
  left.device_id === right.device_id &&
  left.source_mode === right.source_mode &&
  left.status === right.status &&
  left.protocol_version === right.protocol_version &&
  left.device_session_id === right.device_session_id &&
  left.last_status_code === right.last_status_code &&
  left.last_transition_monotonic_s === right.last_transition_monotonic_s

const reconcileDevices = (
  previous: DevicesState,
  next: DevicesState
): DevicesState => {
  const registry = {
    button_pad: registryEntryEqual(
      previous.registry.button_pad,
      next.registry.button_pad
    )
      ? previous.registry.button_pad
      : next.registry.button_pad,
    servotronic_controller: registryEntryEqual(
      previous.registry.servotronic_controller,
      next.registry.servotronic_controller
    )
      ? previous.registry.servotronic_controller
      : next.registry.servotronic_controller,
  }
  if (
    registry.button_pad === previous.registry.button_pad &&
    registry.servotronic_controller === previous.registry.servotronic_controller &&
    previous.networks === next.networks
  ) {
    return previous
  }
  return { registry, networks: next.networks }
}

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
        lighting: envelope.data.lighting,
        devices: reconcileDevices(current.devices, envelope.data.devices),
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
    applyLighting: (envelope) => applyTopic("lighting", "lighting", envelope),
    applyDevices: (envelope) => {
      const current = get()
      if (envelope.protocol_version !== LIVE_PROTOCOL_VERSION) {
        return applyTopic("devices", "devices", envelope)
      }
      if (
        current.bootId !== envelope.boot_id ||
        envelope.revision <= current.topicRevisions.devices
      ) {
        return applyTopic("devices", "devices", envelope)
      }
      set({
        devices: reconcileDevices(current.devices, envelope.data),
        topicRevisions: {
          ...current.topicRevisions,
          devices: envelope.revision,
        },
      })
      return "applied"
    },
    applyHealth: (envelope) => applyTopic("health", "health", envelope),
    reset: () => set({ ...emptySlices(), connection: initialConnection() }),
  }
})
