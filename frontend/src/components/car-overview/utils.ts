import type { StoredSteeringProfile } from "../../api/steering.ts"
import type { ApplicationSnapshot } from "../simulator-workbench/types.ts"
import { definitionsEqual } from "../steering-curve-editor/utils.ts"

export const steeringModeLabel = (
  application: Pick<
    ApplicationSnapshot,
    "maximum_assistance_active" | "steering_mode"
  >
) =>
  application.maximum_assistance_active
    ? "Maximum"
    : application.steering_mode === "manual"
      ? "Manual"
      : "Auto"

export const activeProfileLabel = ({
  application,
  profiles,
  catalogAvailable,
}: {
  application: ApplicationSnapshot
  profiles: readonly StoredSteeringProfile[]
  catalogAvailable: boolean
}) => {
  const active = application.active_steering_curve
  if (active === null) return "Active curve unavailable"
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
