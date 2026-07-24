import type { QueryClient } from "@tanstack/react-query"

import {
  getApplicationSettingsQueryKey,
  getButtonProfileQueryKey,
  getSavedButtonProfileQueryKey,
  getSavedSteeringProfileQueryKey,
  getSteeringProfileQueryKey,
  listButtonProfilesQueryKey,
  listSteeringProfilesQueryKey,
} from "./http/@tanstack/react-query.gen"
import type { ResourceChangedEvent } from "./live-contract.gen"

const steeringQueryIds = new Set([
  getSavedSteeringProfileQueryKey()[0]._id,
  listSteeringProfilesQueryKey()[0]._id,
  getSteeringProfileQueryKey({ path: { profile_id: "" } })[0]._id,
])
const buttonQueryIds = new Set([
  getSavedButtonProfileQueryKey()[0]._id,
  listButtonProfilesQueryKey()[0]._id,
  getButtonProfileQueryKey({ path: { profile_id: "" } })[0]._id,
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
  const buttonProfile = event.resource === "button_profile"
  const invalidations: Promise<unknown>[] = [
    queryClient.invalidateQueries({
      queryKey: buttonProfile
        ? getSavedButtonProfileQueryKey()
        : getSavedSteeringProfileQueryKey(),
      exact: true,
    }),
    queryClient.invalidateQueries({
      queryKey: buttonProfile
        ? listButtonProfilesQueryKey()
        : listSteeringProfilesQueryKey(),
      exact: true,
    }),
  ]
  if (event.id !== null) {
    invalidations.push(
      queryClient.invalidateQueries({
        queryKey: buttonProfile
          ? getButtonProfileQueryKey({ path: { profile_id: event.id } })
          : getSteeringProfileQueryKey({ path: { profile_id: event.id } }),
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
        (steeringQueryIds.has(queryKey[0]._id) ||
          buttonQueryIds.has(queryKey[0]._id)),
    }),
  ])
