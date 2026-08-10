import type { ApiProblemResponse } from "@e87canbus/coordinator-client/api/http"

export const buttonProfileErrorDetail = (error: unknown): string => {
  if (typeof error === "object" && error !== null) {
    const body = (error as { body?: ApiProblemResponse }).body
    if (body?.error.message) return body.error.message
  }
  return error instanceof Error ? error.message : "The request failed."
}
