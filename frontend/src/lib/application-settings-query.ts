import { useQuery } from "@tanstack/react-query"

import { getApplicationSettingsOptions } from "@/api/http/@tanstack/react-query.gen"
import type { ApplicationSettingsResponse } from "@/api/http/types.gen"
import { DEFAULT_APPLICATION_SETTINGS } from "./application-settings"

export type EffectiveApplicationSettings = {
  settings: ApplicationSettingsResponse
  isAuthoritative: boolean
  persistenceFault: boolean
  canSave: boolean
}

export const resolveEffectiveApplicationSettings = (
  settings: ApplicationSettingsResponse | undefined,
  loadFailed: boolean
): EffectiveApplicationSettings => {
  if (settings !== undefined) {
    return {
      settings,
      isAuthoritative: true,
      persistenceFault: false,
      canSave: true,
    }
  }
  return {
    settings: DEFAULT_APPLICATION_SETTINGS,
    isAuthoritative: false,
    persistenceFault: loadFailed,
    canSave: false,
  }
}

export const useEffectiveApplicationSettings = () => {
  const query = useQuery(getApplicationSettingsOptions())
  return {
    ...resolveEffectiveApplicationSettings(query.data, query.isError),
    error: query.error,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    refetch: async () => {
      await query.refetch()
    },
  }
}
