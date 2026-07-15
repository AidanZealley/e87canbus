import { queryOptions } from "@tanstack/react-query"

import type { CommandAcknowledgement } from "./commands.ts"
import { ApiError, requestApi } from "./client.ts"
import type { SteeringState } from "./live-events.ts"
import { DURABLE_STALE_TIME_MS } from "./query-policy.ts"

export type ActiveSteeringCurve = SteeringState["active_curve"]
export type SteeringCurveDefinition = ActiveSteeringCurve["definition"]

export type StoredSteeringProfile = {
  profile_id: string
  name: string
  revision: number
  definition: SteeringCurveDefinition
  created_at: string
  updated_at: string
}

export const steeringProfilesQueryKey = ["steering-profiles", "list"] as const
export const steeringProfileQueryKey = (profileId: string) =>
  ["steering-profiles", "detail", profileId] as const

export const listSteeringProfiles = async () => {
  const response = await requestApi<{ profiles: StoredSteeringProfile[] }>(
    "/api/steering/profiles",
    "Steering"
  )
  return response.profiles
}

export const steeringProfilesQueryOptions = () =>
  queryOptions({
    queryKey: steeringProfilesQueryKey,
    queryFn: listSteeringProfiles,
    staleTime: DURABLE_STALE_TIME_MS,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

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
) => {
  if (savedProfile !== undefined) {
    return requestApi<CommandAcknowledgement>(
      "/api/commands/activate-steering-profile",
      "Steering",
      {
        method: "POST",
        body: JSON.stringify({
          profile_id: savedProfile.profile_id,
          expected_revision: savedProfile.revision,
        }),
      }
    )
  }
  return requestApi<CommandAcknowledgement>(
    "/api/commands/steering-curve",
    "Steering",
    {
      method: "PUT",
      body: JSON.stringify({ definition }),
    }
  )
}

export { ApiError as SteeringApiError }
