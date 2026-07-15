export const LIVE_PROTOCOL_VERSION = 1 as const

export type TopicName =
  "vehicle" | "engine" | "steering" | "buttons" | "devices" | "health"

export type TopicRevisions = Record<TopicName, number>

export type LiveEnvelope<T> = {
  protocol_version: typeof LIVE_PROTOCOL_VERSION
  boot_id: string
  revision: number
  emitted_at: string
  data: T
}

export type VehicleState = {
  speed_kph: number
  speed_valid: boolean
}

export type EngineTelemetryValue = {
  value: number | null
  status: "valid" | "never_observed" | "stale"
}

export type EngineState = {
  rpm: EngineTelemetryValue
  oil_temperature_c: EngineTelemetryValue
  coolant_temperature_c: EngineTelemetryValue
}

export type SteeringCurvePoint = {
  speed_deci_kph: number
  assistance_per_mille: number
}

export type SteeringState = {
  mode: "auto" | "manual"
  manual_assistance_level: number
  maximum_assistance_active: boolean
  active_curve: {
    definition: {
      schema_version: 1
      interpolation: "linear-v1" | "monotone-cubic-v1"
      points: SteeringCurvePoint[]
    }
    fingerprint: string
    activation_revision: number
    status: "active" | "activating" | "activation_failed"
    saved_profile_id: string | null
    saved_profile_revision: number | null
    supported_interpolations: Array<"linear-v1" | "monotone-cubic-v1">
  }
}

export type ButtonsState = {
  led_colours: number[]
  next_pressed: boolean | null
}

export type DevicesState = {
  devices: Array<{
    id: "button_pad" | "steering_controller"
    label: string
    status: "online" | "degraded" | "offline"
    reason: "simulated_degraded" | "simulated_offline" | null
  }>
  networks: Array<{
    id: "kcan" | "ptcan" | "fcan"
    label: string
    interface: string
    bitrate: number
    connected: boolean
    nodes: string[]
  }>
  steering_controller: {
    effective_assistance: number
    last_command_reason:
      | "auto"
      | "manual"
      | "maximum"
      | "speed_never_observed"
      | "speed_stale"
      | "can_reader_failure"
      | "inbox_overflow"
      | "shutdown"
      | null
    watchdog_timed_out: boolean
  } | null
}

export type RuntimeFaultState = {
  kind:
    | "can_reader"
    | "can_effect_execution"
    | "steering_actuator"
    | "inbox_overflow"
  monotonic_s: number
  message: string
}

export type ControllerHealthState = {
  lifecycle: "created" | "running" | "stopped"
  fatal: boolean
  networks: Array<{
    network: "kcan" | "ptcan" | "fcan"
    fault: RuntimeFaultState | null
  }>
  steering_actuator_fault: RuntimeFaultState | null
}

export type ControllerSnapshotData = {
  topic_revisions: TopicRevisions
  simulation_session_id: number | null
  vehicle: VehicleState
  engine: EngineState
  steering: SteeringState
  buttons: ButtonsState
  devices: DevicesState
  health: ControllerHealthState
}

export type ResourceChangedEvent = {
  type: "resources.changed"
  resource: "settings" | "steering_profile"
  id: string | null
  revision: number
}

export type TraceRow = {
  type: "frame"
  session_id: number
  sequence: number
  network: "kcan" | "ptcan" | "fcan"
  source: string
  arbitration_id: number
  arbitration_id_hex: string
  data_hex: string
  is_extended_id: boolean
  monotonic_s: number
}

export type TraceBatch = { rows: TraceRow[] }

export type ServerToClientEvents = {
  "controller.snapshot": (payload: LiveEnvelope<ControllerSnapshotData>) => void
  "vehicle.state": (payload: LiveEnvelope<VehicleState>) => void
  "engine.state": (payload: LiveEnvelope<EngineState>) => void
  "steering.state": (payload: LiveEnvelope<SteeringState>) => void
  "buttons.state": (payload: LiveEnvelope<ButtonsState>) => void
  "devices.state": (payload: LiveEnvelope<DevicesState>) => void
  "controller.health": (payload: LiveEnvelope<ControllerHealthState>) => void
  "resources.changed": (payload: ResourceChangedEvent) => void
  "trace.batch": (payload: LiveEnvelope<TraceBatch>) => void
}

export type ClientToServerEvents = {
  "controller.resync": () => void
  "trace.subscribe": () => void
  "trace.unsubscribe": () => void
}
