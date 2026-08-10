import type { QueryClientConfig } from "@tanstack/react-query"

export const consoleQueryClientOptions = {
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
    mutations: {
      networkMode: "always",
      retry: false,
    },
  },
} satisfies QueryClientConfig
