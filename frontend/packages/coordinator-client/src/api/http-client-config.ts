import type { CreateClientConfig } from "./http/client.gen"

export const COORDINATOR_ORIGIN =
  import.meta.env?.VITE_COORDINATOR_ORIGIN ??
  (import.meta.env?.DEV ? "http://127.0.0.1:8000" : window.location.origin)

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: COORDINATOR_ORIGIN,
})
