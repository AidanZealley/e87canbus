import assert from "node:assert/strict"
import test from "node:test"

import type {
  ActiveSteeringCurve,
  SteeringCurveDefinition,
  StoredSteeringProfile,
} from "../../api/steering.ts"
import { emptySnapshot } from "../simulator-workbench/utils.ts"
import { activeProfileLabel, steeringModeLabel } from "./utils.ts"

const definition: SteeringCurveDefinition = {
  schema_version: 1,
  interpolation: "linear-v1",
  points: [0, 100, 200, 300, 600, 1000, 1600, 2500].map(
    (speed_deci_kph, index) => ({
      speed_deci_kph,
      assistance_per_mille: [1000, 890, 780, 670, 380, 0, 0, 0][index] ?? 0,
    })
  ),
}
const active: ActiveSteeringCurve = {
  definition,
  fingerprint: "active",
  activation_revision: 2,
  status: "active",
  saved_profile_id: "11111111-1111-4111-8111-111111111111",
  saved_profile_revision: 3,
  supported_interpolations: ["linear-v1", "monotone-cubic-v1"],
}
const profile: StoredSteeringProfile = {
  profile_id: active.saved_profile_id!,
  name: "Dry track",
  revision: 3,
  definition,
  created_at: "2026-07-14T00:00:00.000000Z",
  updated_at: "2026-07-14T00:00:00.000000Z",
}

test("labels Auto, Manual and temporary Maximum modes", () => {
  assert.equal(
    steeringModeLabel({
      steering_mode: "auto",
      maximum_assistance_active: false,
    }),
    "Auto"
  )
  assert.equal(
    steeringModeLabel({
      steering_mode: "manual",
      maximum_assistance_active: false,
    }),
    "Manual"
  )
  assert.equal(
    steeringModeLabel({
      steering_mode: "manual",
      maximum_assistance_active: true,
    }),
    "Maximum"
  )
})

test("distinguishes matching, modified, unsaved and unavailable profile provenance", () => {
  const application = {
    ...emptySnapshot.application,
    active_steering_curve: active,
  }
  assert.equal(
    activeProfileLabel({
      application,
      profiles: [profile],
      catalogAvailable: true,
    }),
    "Dry track"
  )
  assert.equal(
    activeProfileLabel({
      application,
      profiles: [{ ...profile, revision: 4 }],
      catalogAvailable: true,
    }),
    "Modified"
  )
  assert.equal(
    activeProfileLabel({
      application: {
        ...application,
        active_steering_curve: {
          ...active,
          saved_profile_id: null,
          saved_profile_revision: null,
        },
      },
      profiles: [],
      catalogAvailable: true,
    }),
    "Unsaved curve"
  )
  assert.equal(
    activeProfileLabel({ application, profiles: [], catalogAvailable: false }),
    "Profile unavailable · active curve retained"
  )
})
