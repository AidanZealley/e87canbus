import type { StoredSteeringProfile } from "../../api/steering.ts"
import type { SteeringState } from "../../api/live-events.ts"
import { definitionsEqual } from "../steering-curve-editor/utils.ts"

export const steeringModeLabel = (
  steering: Pick<SteeringState, "maximum_assistance_active" | "mode">
) =>
  steering.maximum_assistance_active
    ? "Maximum"
    : steering.mode === "manual"
      ? "Manual"
      : "Auto"

export const activeProfileLabel = ({
  steering,
  profiles,
  catalogAvailable,
}: {
  steering: SteeringState
  profiles: readonly StoredSteeringProfile[]
  catalogAvailable: boolean
}) => {
  const active = steering.active_curve
  if (!catalogAvailable) {
    return active.saved_profile_id === null
      ? "Unsaved curve"
      : "Profile unavailable · active curve retained"
  }
  if (
    active.saved_profile_id === null ||
    active.saved_profile_revision === null
  ) {
    return "Unsaved curve"
  }
  const profile = profiles.find(
    (candidate) => candidate.profile_id === active.saved_profile_id
  )
  if (
    profile !== undefined &&
    profile.revision === active.saved_profile_revision &&
    definitionsEqual(profile.definition, active.definition)
  ) {
    return profile.name
  }
  return "Modified"
}
