import type {
  SnapshotEvent,
  SteeringCurveDefinition,
} from "@e87canbus/coordinator-client/api/http/types.gen"

const steering = {
  mode: "auto" as const,
  manual_assistance_level: 0,
  manual_assistance_level_count: 11,
  maximum_assistance_active: false,
  active_curve: {
    definition: {
      schema_version: 1 as const,
      points: [0, 100, 200, 300, 600, 1000, 1600, 2500].map(
        (speed_deci_kph, index) => ({
          speed_deci_kph,
          assistance_per_mille: Math.max(0, 1000 - index * 140),
        })
      ) as SteeringCurveDefinition["points"],
    },
    fingerprint: "curve",
    activation_revision: 1,
    status: "active" as const,
    saved_profile_id: null,
    saved_profile_revision: null,
  },
  servotronic: null,
  curve_activation_available: true,
}

export const snapshot = (revision: number): SnapshotEvent => ({
  type: "snapshot",
  data: {
    vehicle: { speed_kph: revision, speed_valid: true },
    engine: {
      rpm: { value: 1000, status: "valid" },
      oil_temperature_c: { value: 90, status: "valid" },
      coolant_temperature_c: { value: 80, status: "valid" },
    },
    steering,
    buttons: {
      active_profile_id: "00000000-0000-4000-8000-000000000002",
      active_profile_revision: revision || null,
    },
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
      devices: [
        { role: "servotronic_controller", fault: null },
      ],
      steering: { fault: null },
      persistence: { available: true, fault: null },
    },
  },
})
