import type {
  ControllerSnapshotData,
  LiveEnvelope,
} from "@/api/live-events"

const steering = {
  mode: "auto" as const,
  manual_assistance_level: 0,
  maximum_assistance_active: false,
  active_curve: {
    definition: {
      schema_version: 1 as const,
      points: [0, 100, 200, 300, 600, 1000, 1600, 2500].map(
        (speed_deci_kph, index) => ({
          speed_deci_kph,
          assistance_per_mille: Math.max(0, 1000 - index * 140),
        })
      ),
    },
    fingerprint: "curve",
    activation_revision: 1,
    status: "active" as const,
    saved_profile_id: null,
    saved_profile_revision: null,
  },
}

export const snapshot = (
  bootId: string,
  revision: number
): LiveEnvelope<ControllerSnapshotData> => ({
  protocol_version: 1,
  boot_id: bootId,
  revision,
  emitted_at: "2026-07-15T00:00:00Z",
  data: {
    topic_revisions: {
      vehicle: revision,
      engine: revision,
      steering: revision,
      buttons: revision,
      devices: revision,
      health: revision,
    },
    simulation_session_id: revision,
    vehicle: { speed_kph: revision, speed_valid: true },
    engine: {
      rpm: { value: 1000, status: "valid" },
      oil_temperature_c: { value: 90, status: "valid" },
      coolant_temperature_c: { value: 80, status: "valid" },
    },
    steering,
    buttons: {
      led_colours: Array<number>(16).fill(revision),
    },
    devices: { devices: [], networks: [], steering_controller: null },
    health: {
      ready: true,
      fatal: false,
      networks: [],
      inbox: {
        depth: 0,
        capacity: 1024,
        current_latency_s: 0,
        latency_warning: false,
        overflow_latched: false,
      },
      devices: [],
      steering: {
        fault: null,
      },
      persistence: { available: true, fault: null },
      publisher: {
        running: true,
        failures: 0,
        trace_rows_dropped: 0,
        resource_changes_dropped: 0,
        transport_queue_saturations: 0,
        fault: null,
      },
    },
  },
})
