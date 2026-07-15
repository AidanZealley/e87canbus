import type { QueryClient } from "@tanstack/react-query"

import { applicationSettingsQueryKey } from "../../api/settings.ts"
import {
  steeringProfileQueryKey,
  steeringProfilesQueryKey,
} from "../../api/steering.ts"
import type { ResourceChangedEvent, SimulatorSocketEvent } from "./types.ts"

export const handleResourceInvalidationEvent = (
  queryClient: QueryClient,
  event: SimulatorSocketEvent
): event is ResourceChangedEvent => {
  if (event.type !== "resources.changed") return false
  if (event.resource === "settings") {
    void queryClient.invalidateQueries({ queryKey: applicationSettingsQueryKey })
    return true
  }
  void queryClient.invalidateQueries({ queryKey: steeringProfilesQueryKey })
  if (event.id !== null) {
    void queryClient.invalidateQueries({
      queryKey: steeringProfileQueryKey(event.id),
    })
  }
  return true
}
