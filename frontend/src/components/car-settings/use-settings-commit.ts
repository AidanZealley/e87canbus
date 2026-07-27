import { useRef } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  getApplicationSettingsQueryKey,
  updateApplicationSettingsMutation,
} from "@/api/http/@tanstack/react-query.gen"
import type { ApplicationSettingsResponse } from "@/api/http/types.gen"
import { isApiProblemResponse } from "@/api/is-api-problem"
import type { ApplicationSettingsValues } from "./types"
import { settingsToValues, valuesToRequest } from "./utils"

const settingsErrorDetail = (error: unknown): string => {
  if (isApiProblemResponse(error)) return error.error.message
  return error instanceof Error ? error.message : "The request failed."
}

/**
 * Every edit is written straight through. Commits are queued so a burst of
 * changes cannot race the revision each of them expects.
 */
export const useSettingsCommit = (settings: ApplicationSettingsResponse) => {
  const queryClient = useQueryClient()
  const update = useMutation({
    ...updateApplicationSettingsMutation(),
    onSuccess: (committed) =>
      queryClient.setQueryData(getApplicationSettingsQueryKey(), committed),
  })
  const queue = useRef<Promise<void>>(Promise.resolve())

  const commit = (patch: Partial<ApplicationSettingsValues>) => {
    const run = queue.current.then(async () => {
      const current =
        queryClient.getQueryData<ApplicationSettingsResponse>(
          getApplicationSettingsQueryKey()
        ) ?? settings
      try {
        await update.mutateAsync({
          body: valuesToRequest(
            { ...settingsToValues(current), ...patch },
            current.revision
          ),
        })
        // Each save raises its own toast: reusing one id updates it silently,
        // which reads as nothing having happened when edits come in a run.
        toast.success("Settings saved")
      } catch (error) {
        if (
          isApiProblemResponse(error) &&
          error.error.code === "settings_revision_conflict"
        ) {
          await queryClient.invalidateQueries({
            queryKey: getApplicationSettingsQueryKey(),
          })
          toast.error("Settings changed elsewhere — reloaded the latest")
        } else {
          toast.error(settingsErrorDetail(error))
        }
      }
    })
    queue.current = run
    return run
  }

  return { commit }
}
