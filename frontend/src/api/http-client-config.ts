import type { CreateClientConfig } from "./http/client.gen"

export const API_BASE =
  import.meta.env?.VITE_API_BASE ?? "http://127.0.0.1:8000"

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: API_BASE,
})
