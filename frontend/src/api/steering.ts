export type SteeringCurvePoint = {
  speed_deci_kph: number
  assistance_per_mille: number
}

export type SteeringCurveDefinition = {
  schema_version: 1
  interpolation: "linear-v1"
  points: SteeringCurvePoint[]
}

export type ActiveSteeringCurve = {
  definition: SteeringCurveDefinition
  fingerprint: string
  activation_revision: number
  status: "active" | "activating" | "activation_failed"
  saved_profile_id: string | null
  saved_profile_revision: number | null
}

export type StoredSteeringProfile = {
  profile_id: string
  name: string
  revision: number
  definition: SteeringCurveDefinition
  created_at: string
  updated_at: string
}

type ApiProblemBody = {
  error?: {
    code?: string
    message?: string
    current_revision?: number
  }
}

export class SteeringApiError extends Error {
  readonly status: number
  readonly code: string
  readonly currentRevision?: number

  constructor(
    status: number,
    code: string,
    message: string,
    currentRevision?: number
  ) {
    super(message)
    this.name = "SteeringApiError"
    this.status = status
    this.code = code
    this.currentRevision = currentRevision
  }
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000"

export const steeringProfilesQueryKey = ["steering-profiles"] as const

const request = async <Response>(
  path: string,
  init?: RequestInit
): Promise<Response> => {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })

  if (!response.ok) {
    let problem: ApiProblemBody = {}
    try {
      problem = (await response.json()) as ApiProblemBody
    } catch {
      // The typed fallback remains actionable if a proxy returns a non-JSON error.
    }
    throw new SteeringApiError(
      response.status,
      problem.error?.code ?? "request_failed",
      problem.error?.message ??
        `Steering API request failed: ${response.status}`,
      problem.error?.current_revision
    )
  }

  if (response.status === 204) {
    return undefined as Response
  }
  return response.json() as Promise<Response>
}

export const listSteeringProfiles = async () => {
  const response = await request<{ profiles: StoredSteeringProfile[] }>(
    "/api/steering/profiles"
  )
  return response.profiles
}

export const createSteeringProfile = (
  name: string,
  definition: SteeringCurveDefinition
) =>
  request<StoredSteeringProfile>("/api/steering/profiles", {
    method: "POST",
    body: JSON.stringify({ name, definition }),
  })

export const updateSteeringProfile = (
  profile: StoredSteeringProfile,
  definition: SteeringCurveDefinition
) =>
  request<StoredSteeringProfile>(
    `/api/steering/profiles/${profile.profile_id}`,
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
  request<void>(
    `/api/steering/profiles/${profile.profile_id}?expected_revision=${profile.revision}`,
    { method: "DELETE" }
  )

export const activateSteeringCurve = (
  definition: SteeringCurveDefinition,
  savedProfile?: StoredSteeringProfile
) =>
  request<ActiveSteeringCurve>("/api/steering/curve-state/activate", {
    method: "POST",
    body: JSON.stringify({
      definition,
      saved_profile_id: savedProfile?.profile_id ?? null,
      saved_profile_revision: savedProfile?.revision ?? null,
    }),
  })
