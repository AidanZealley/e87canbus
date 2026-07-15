import type { QueryClient } from "@tanstack/react-query"

import { applicationSettingsQueryKey } from "./settings"
import { steeringProfileQueryKey, steeringProfilesQueryKey } from "./steering"
import type { ResourceChangedEvent } from "./live-events"

export const invalidateChangedResource = (
  queryClient: QueryClient,
  event: ResourceChangedEvent
) => {
  if (event.resource === "settings") {
    return queryClient.invalidateQueries({
      queryKey: applicationSettingsQueryKey,
      exact: true,
    })
  }
  const invalidations: Promise<unknown>[] = [
    queryClient.invalidateQueries({
      queryKey: steeringProfilesQueryKey,
      exact: true,
    }),
  ]
  if (event.id !== null) {
    invalidations.push(
      queryClient.invalidateQueries({
        queryKey: steeringProfileQueryKey(event.id),
        exact: true,
      })
    )
  }
  return Promise.all(invalidations)
}

export const reconcileDurableResources = (queryClient: QueryClient) =>
  Promise.all([
    queryClient.invalidateQueries({
      queryKey: applicationSettingsQueryKey,
      exact: true,
    }),
    queryClient.invalidateQueries({ queryKey: ["steering-profiles"] }),
  ])
