import { QueryClient } from "@tanstack/react-query"
import { expect, it } from "vitest"

import {
  invalidateChangedResource,
  reconcileDurableResources,
} from "./durable-query-ownership"
import {
  getApplicationSettingsQueryKey,
  getSavedSteeringProfileQueryKey,
  getSteeringProfileQueryKey,
  listSteeringProfilesQueryKey,
} from "./http/@tanstack/react-query.gen"

it("invalidates only the exact resource keys named by a resource event", async () => {
  const queryClient = new QueryClient()
  const settings = getApplicationSettingsQueryKey()
  const profiles = listSteeringProfilesQueryKey()
  const savedProfile = getSavedSteeringProfileQueryKey()
  const target = getSteeringProfileQueryKey({ path: { profile_id: "target" } })
  const other = getSteeringProfileQueryKey({ path: { profile_id: "other" } })
  for (const key of [settings, profiles, savedProfile, target, other]) {
    queryClient.setQueryData(key, {})
  }
  await invalidateChangedResource(queryClient, {
    type: "resources.changed",
    resource: "steering_profile",
    id: "target",
    revision: 2,
  })
  expect(queryClient.getQueryState(profiles)?.isInvalidated).toBe(true)
  expect(queryClient.getQueryState(savedProfile)?.isInvalidated).toBe(true)
  expect(queryClient.getQueryState(target)?.isInvalidated).toBe(true)
  expect(queryClient.getQueryState(other)?.isInvalidated).toBe(false)
  expect(queryClient.getQueryState(settings)?.isInvalidated).toBe(false)
})

it("reconciles only the known durable roots after a complete reconnect snapshot", async () => {
  const queryClient = new QueryClient()
  const settings = getApplicationSettingsQueryKey()
  const profiles = listSteeringProfilesQueryKey()
  const savedProfile = getSavedSteeringProfileQueryKey()
  const profile = getSteeringProfileQueryKey({
    path: { profile_id: "profile" },
  })
  const unrelated = ["unrelated"] as const
  for (const key of [settings, profiles, savedProfile, profile, unrelated]) {
    queryClient.setQueryData(key, {})
  }
  await reconcileDurableResources(queryClient)
  expect(queryClient.getQueryState(settings)?.isInvalidated).toBe(true)
  expect(queryClient.getQueryState(profiles)?.isInvalidated).toBe(true)
  expect(queryClient.getQueryState(savedProfile)?.isInvalidated).toBe(true)
  expect(queryClient.getQueryState(profile)?.isInvalidated).toBe(true)
  expect(queryClient.getQueryState(unrelated)?.isInvalidated).toBe(false)
})
