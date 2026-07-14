import type { QueryClient } from "@tanstack/react-query"

import { applicationSettingsQueryKey } from "../../api/settings.ts"
import { steeringProfilesQueryKey } from "../../api/steering.ts"
import type {
  ApplicationSettingsChangedEvent,
  SimulatorSocketEvent,
  SteeringProfileCatalogChangedEvent,
} from "./types.ts"

type ResourceInvalidationEvent =
  | SteeringProfileCatalogChangedEvent
  | ApplicationSettingsChangedEvent

export const handleResourceInvalidationEvent = (
  queryClient: QueryClient,
  event: SimulatorSocketEvent
): event is ResourceInvalidationEvent => {
  if (event.type === "steering_profile_catalog_changed") {
    void queryClient.invalidateQueries({ queryKey: steeringProfilesQueryKey })
    return true
  }
  if (event.type === "application_settings_changed") {
    void queryClient.invalidateQueries({ queryKey: applicationSettingsQueryKey })
    return true
  }
  return false
}
