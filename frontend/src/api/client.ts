type ApiProblemBody = {
  error?: {
    code?: string
    message?: string
    current_revision?: number
    supported_interpolations?: string[]
  }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly currentRevision?: number
  readonly supportedInterpolations?: string[]

  constructor(
    status: number,
    code: string,
    message: string,
    currentRevision?: number,
    supportedInterpolations?: string[]
  ) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.currentRevision = currentRevision
    this.supportedInterpolations = supportedInterpolations
  }
}

const API_BASE = import.meta.env?.VITE_API_BASE ?? "http://127.0.0.1:8000"

export const requestApi = async <Response>(
  path: string,
  resourceName: string,
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
      // A typed fallback remains actionable when a proxy returns non-JSON.
    }
    throw new ApiError(
      response.status,
      problem.error?.code ?? "request_failed",
      problem.error?.message ??
        `${resourceName} API request failed: ${response.status}`,
      problem.error?.current_revision,
      problem.error?.supported_interpolations
    )
  }

  if (response.status === 204) return undefined as Response
  return response.json() as Promise<Response>
}
