import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { RouterProvider } from "@tanstack/react-router"

import "./index.css"
import { ThemeProvider } from "@/components/theme-provider.tsx"
import {
  getApplicationSettingsQueryKey,
  getSavedSteeringProfileQueryKey,
  listSteeringProfilesQueryKey,
} from "@/api/http/@tanstack/react-query.gen"
import { Toaster } from "@/components/ui/sonner"
import { startLiveTransport } from "@/live/transport"
import { router } from "@/router"

if (import.meta.env.DEV) {
  window.setInterval(() => performance.clearMeasures(), 60_000)
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
})

const durableQueryDefaults = {
  staleTime: 30_000,
  refetchOnReconnect: false,
  refetchOnWindowFocus: false,
}
queryClient.setQueryDefaults(
  getApplicationSettingsQueryKey(),
  durableQueryDefaults
)
queryClient.setQueryDefaults(
  listSteeringProfilesQueryKey(),
  durableQueryDefaults
)
queryClient.setQueryDefaults(
  getSavedSteeringProfileQueryKey(),
  durableQueryDefaults
)

startLiveTransport(queryClient)

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <RouterProvider router={router} />
        <Toaster />
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>
)
