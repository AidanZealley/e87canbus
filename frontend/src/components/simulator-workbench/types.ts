export type CanTraceEntry = {
  type: "frame"
  source: string
  arbitration_id: number
  arbitration_id_hex: string
  data_hex: string
  is_extended_id: boolean
  monotonic_s: number
}

export type ApplicationSnapshot = {
  vehicle_speed_kph: number
  steering_mode: "auto" | "manual"
  manual_assistance_level: number
  strobe_active: boolean
}

export type SimulatorSnapshot = {
  application: ApplicationSnapshot
  next_pressed: boolean
  led_colours: Record<string, number>
  trace: CanTraceEntry[]
}

export type SnapshotEvent = {
  type: "snapshot"
  snapshot: SimulatorSnapshot
}

export type LedUpdateEvent = {
  type: "led_update"
  button_index: number
  colour_code: number
  colour_name: string
}

export type SimulatorEvent = SnapshotEvent | CanTraceEntry | LedUpdateEvent
