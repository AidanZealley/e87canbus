import type { CreateClientConfig } from "./http/client.gen"

export const API_BASE =
  import.meta.env?.VITE_API_BASE ??
  (import.meta.env?.DEV ? "http://127.0.0.1:8000" : window.location.origin)

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: API_BASE,
})
