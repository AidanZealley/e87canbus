import { ApiError, requestApi } from "./client.ts"

export type SteeringCurvePoint = {
  speed_deci_kph: number
  assistance_per_mille: number
}

export type SteeringCurveDefinition = {
  schema_version: 1
  interpolation: SteeringCurveInterpolation
  points: SteeringCurvePoint[]
}

export type SteeringCurveInterpolation = "linear-v1" | "monotone-cubic-v1"

export type ActiveSteeringCurve = {
  definition: SteeringCurveDefinition
  fingerprint: string
  activation_revision: number
  status: "active" | "activating" | "activation_failed"
  saved_profile_id: string | null
  saved_profile_revision: number | null
  supported_interpolations: SteeringCurveInterpolation[]
}

export type StoredSteeringProfile = {
  profile_id: string
  name: string
  revision: number
  definition: SteeringCurveDefinition
  created_at: string
  updated_at: string
}

export const steeringProfilesQueryKey = ["steering-profiles"] as const

export const listSteeringProfiles = async () => {
  const response = await requestApi<{ profiles: StoredSteeringProfile[] }>(
    "/api/steering/profiles",
    "Steering"
  )
  return response.profiles
}

export const createSteeringProfile = (
  name: string,
  definition: SteeringCurveDefinition
) =>
  requestApi<StoredSteeringProfile>("/api/steering/profiles", "Steering", {
    method: "POST",
    body: JSON.stringify({ name, definition }),
  })

export const updateSteeringProfile = (
  profile: StoredSteeringProfile,
  definition: SteeringCurveDefinition
) =>
  requestApi<StoredSteeringProfile>(
    `/api/steering/profiles/${profile.profile_id}`,
    "Steering",
    {
      method: "PUT",
      body: JSON.stringify({
        name: profile.name,
        expected_revision: profile.revision,
        definition,
      }),
    }
  )

export const deleteSteeringProfile = (profile: StoredSteeringProfile) =>
  requestApi<void>(
    `/api/steering/profiles/${profile.profile_id}?expected_revision=${profile.revision}`,
    "Steering",
    { method: "DELETE" }
  )

export const activateSteeringCurve = (
  definition: SteeringCurveDefinition,
  savedProfile?: StoredSteeringProfile
) =>
  requestApi<ActiveSteeringCurve>(
    "/api/steering/curve-state/activate",
    "Steering",
    {
      method: "POST",
      body: JSON.stringify({
        definition,
        saved_profile_id: savedProfile?.profile_id ?? null,
        saved_profile_revision: savedProfile?.revision ?? null,
      }),
    }
  )

export { ApiError as SteeringApiError }
