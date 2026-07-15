import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query"

import {
  applicationSettingsQueryKey,
  applicationSettingsQueryOptions,
  DEFAULT_APPLICATION_SETTINGS,
  updateApplicationSettings,
  type ApplicationSettings,
  type UpdateApplicationSettingsRequest,
} from "../api/settings.ts"

export type EffectiveApplicationSettings = {
  settings: ApplicationSettings
  isAuthoritative: boolean
  persistenceFault: boolean
  canSave: boolean
}

export const resolveEffectiveApplicationSettings = (
  settings: ApplicationSettings | undefined,
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

export const saveApplicationSettings = async (
  queryClient: QueryClient,
  request: UpdateApplicationSettingsRequest
) => {
  const committed = await updateApplicationSettings(request)
  queryClient.setQueryData(applicationSettingsQueryKey, committed)
  return committed
}

export const useEffectiveApplicationSettings = () => {
  const query = useQuery(applicationSettingsQueryOptions())
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

export const useUpdateApplicationSettings = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: UpdateApplicationSettingsRequest) =>
      saveApplicationSettings(queryClient, request),
  })
}
