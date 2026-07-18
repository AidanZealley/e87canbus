import type { QueryClient } from "@tanstack/react-query"

import {
  getApplicationSettingsQueryKey,
  getSteeringProfileQueryKey,
  listSteeringProfilesQueryKey,
} from "./http/@tanstack/react-query.gen"
import type { ResourceChangedEvent } from "./live-contract.gen"

const steeringQueryIds = new Set([
  listSteeringProfilesQueryKey()[0]._id,
  getSteeringProfileQueryKey({ path: { profile_id: "" } })[0]._id,
])

export const invalidateChangedResource = (
  queryClient: QueryClient,
  event: ResourceChangedEvent
) => {
  if (event.resource === "settings") {
    return queryClient.invalidateQueries({
      queryKey: getApplicationSettingsQueryKey(),
      exact: true,
    })
  }
  const invalidations: Promise<unknown>[] = [
    queryClient.invalidateQueries({
      queryKey: listSteeringProfilesQueryKey(),
      exact: true,
    }),
  ]
  if (event.id !== null) {
    invalidations.push(
      queryClient.invalidateQueries({
        queryKey: getSteeringProfileQueryKey({
          path: { profile_id: event.id },
        }),
        exact: true,
      })
    )
  }
  return Promise.all(invalidations)
}

export const reconcileDurableResources = (queryClient: QueryClient) =>
  Promise.all([
    queryClient.invalidateQueries({
      queryKey: getApplicationSettingsQueryKey(),
      exact: true,
    }),
    queryClient.invalidateQueries({
      predicate: ({ queryKey }) =>
        typeof queryKey[0] === "object" &&
        queryKey[0] !== null &&
        "_id" in queryKey[0] &&
        typeof queryKey[0]._id === "string" &&
        steeringQueryIds.has(queryKey[0]._id),
    }),
  ])
