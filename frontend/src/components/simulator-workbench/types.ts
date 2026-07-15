import type { ActiveSteeringCurve } from "@/api/steering"

export type CanNetwork = "kcan" | "ptcan" | "fcan"

export type CanTraceEntry = {
  type: "frame"
  session_id: number
  sequence: number
  network: CanNetwork
  source: string
  arbitration_id: number
  arbitration_id_hex: string
  data_hex: string
  is_extended_id: boolean
  monotonic_s: number
}

export type NetworkStatus = {
  id: CanNetwork
  label: string
  interface: string
  bitrate: number
  connected: boolean
  nodes: string[]
}

export type DeviceId = "button_pad" | "steering_controller"

export type DeviceStatus = "online" | "degraded" | "offline"

export type DeviceSnapshot = {
  id: DeviceId
  label: string
  status: DeviceStatus
  reason: string | null
}

export type ApplicationSnapshot = {
  vehicle_speed_kph: number
  speed_valid: boolean
  engine: EngineTelemetrySnapshot
  steering_mode: "auto" | "manual"
  manual_assistance_level: number
  maximum_assistance_active: boolean
  active_steering_curve: ActiveSteeringCurve | null
}

export type EngineTelemetryStatus = "valid" | "never_observed" | "stale"

export type EngineTelemetryValue = {
  value: number | null
  status: EngineTelemetryStatus
}

export type EngineTelemetrySnapshot = {
  rpm: EngineTelemetryValue
  oil_temperature_c: EngineTelemetryValue
  coolant_temperature_c: EngineTelemetryValue
}

export type SteeringControllerSnapshot = {
  effective_assistance: number
  last_command_reason:
    | null
    | "auto"
    | "manual"
    | "maximum"
    | "speed_never_observed"
    | "speed_stale"
    | "can_reader_failure"
    | "inbox_overflow"
    | "shutdown"
  watchdog_timed_out: boolean
}

export type SimulatorSnapshot = {
  session_id: number
  revision: number
  fatal: boolean
  application: ApplicationSnapshot
  steering_controller: SteeringControllerSnapshot
  next_pressed: boolean
  led_colours: number[]
  devices: DeviceSnapshot[]
  networks: NetworkStatus[]
  trace?: CanTraceEntry[]
}

export type SnapshotEvent = {
  type: "snapshot"
  session_id: number
  revision: number
  snapshot: SimulatorSnapshot
}

export type SimulatorEvent = SnapshotEvent | CanTraceEntry

export type SteeringProfileCatalogChangedEvent = {
  type: "steering_profile_catalog_changed"
}

export type ApplicationSettingsChangedEvent = {
  type: "application_settings_changed"
}

export type SimulatorSocketEvent =
  | SimulatorEvent
  | SteeringProfileCatalogChangedEvent
  | ApplicationSettingsChangedEvent
