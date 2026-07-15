import { useEffect, type ReactNode } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { startLiveTransport } from "@/live/transport"

export const LiveDataProvider = ({ children }: { children: ReactNode }) => {
  const queryClient = useQueryClient()
  useEffect(() => startLiveTransport(queryClient), [queryClient])
  return children
}
