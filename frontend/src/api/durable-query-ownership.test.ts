import { QueryClient } from "@tanstack/react-query"
import { expect, it } from "vitest"

import {
  invalidateChangedResource,
  reconcileDurableResources,
} from "./durable-query-ownership"
import { applicationSettingsQueryKey } from "./settings"
import {
  steeringProfileQueryKey,
  steeringProfilesQueryKey,
} from "./steering"

it("invalidates only the exact resource keys named by a resource event", async () => {
  const queryClient = new QueryClient()
  const target = steeringProfileQueryKey("target")
  const other = steeringProfileQueryKey("other")
  for (const key of [applicationSettingsQueryKey, steeringProfilesQueryKey, target, other]) {
    queryClient.setQueryData(key, {})
  }
  await invalidateChangedResource(queryClient, {
    type: "resources.changed",
    resource: "steering_profile",
    id: "target",
    revision: 2,
  })
  expect(queryClient.getQueryState(steeringProfilesQueryKey)?.isInvalidated).toBe(true)
  expect(queryClient.getQueryState(target)?.isInvalidated).toBe(true)
  expect(queryClient.getQueryState(other)?.isInvalidated).toBe(false)
  expect(queryClient.getQueryState(applicationSettingsQueryKey)?.isInvalidated).toBe(false)
})

it("reconciles only the known durable roots after a complete reconnect snapshot", async () => {
  const queryClient = new QueryClient()
  const profile = steeringProfileQueryKey("profile")
  const unrelated = ["unrelated"] as const
  for (const key of [applicationSettingsQueryKey, steeringProfilesQueryKey, profile, unrelated]) {
    queryClient.setQueryData(key, {})
  }
  await reconcileDurableResources(queryClient)
  expect(queryClient.getQueryState(applicationSettingsQueryKey)?.isInvalidated).toBe(true)
  expect(queryClient.getQueryState(steeringProfilesQueryKey)?.isInvalidated).toBe(true)
  expect(queryClient.getQueryState(profile)?.isInvalidated).toBe(true)
  expect(queryClient.getQueryState(unrelated)?.isInvalidated).toBe(false)
})
