import { useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  activateSteeringCurveMutation,
  activateSteeringProfileMutation,
  adjustManualAssistanceMutation,
  getSavedSteeringProfileOptions,
  getSavedSteeringProfileQueryKey,
  setMaximumAssistanceMutation,
  setSteeringModeMutation,
  updateSteeringProfileMutation,
} from "@/api/http/@tanstack/react-query.gen"
import { isApiProblemResponse } from "@/api/is-api-problem"
import type { ActiveSteeringCurveState, Mode } from "@/api/live-contract.gen"
import { cn } from "@/lib/utils"
import { CurveActionError } from "./components/curve-action-error"
import { CurveActions } from "./components/curve-actions"
import { EditorCurveChart } from "./components/editor-curve-chart"
import type { PendingCurveAction } from "./types"
import { definitionsEqual } from "./utils"

type SteeringCurveEditorProps = {
  activeCurve: ActiveSteeringCurveState
  mode: Mode
  manualAssistanceLevel: number
  manualAssistanceLevelCount: number
  maximumAssistanceActive: boolean
  speedKph: number | null
  activeAssistance?: number | null
  className?: string
  chartClassName?: string
  activationAvailable?: boolean
  modeControlAvailable?: boolean
}

export const SteeringCurveEditor = ({
  activeCurve,
  mode,
  manualAssistanceLevel,
  manualAssistanceLevelCount,
  maximumAssistanceActive,
  speedKph,
  activeAssistance = null,
  className,
  chartClassName,
  activationAvailable = true,
  modeControlAvailable = true,
}: SteeringCurveEditorProps) => {
  const queryClient = useQueryClient()
  const { data: savedProfile = null } = useQuery({
    ...getSavedSteeringProfileOptions(),
    retry: false,
  })
  const { mutateAsync: activateCurve } = useMutation(
    activateSteeringCurveMutation()
  )
  const { mutateAsync: activateProfile } = useMutation(
    activateSteeringProfileMutation()
  )
  const { mutateAsync: setMode } = useMutation(setSteeringModeMutation())
  const { mutateAsync: adjustManualAssistance } = useMutation(
    adjustManualAssistanceMutation()
  )
  const { mutateAsync: setMaximumAssistance } = useMutation(
    setMaximumAssistanceMutation()
  )
  const { mutateAsync: updateProfile } = useMutation({
    ...updateSteeringProfileMutation(),
    onSuccess: (saved) =>
      queryClient.setQueryData(getSavedSteeringProfileQueryKey(), saved),
    onError: (error) => {
      if (
        isApiProblemResponse(error) &&
        error.error.code === "profile_revision_conflict"
      ) {
        return queryClient.invalidateQueries({
          queryKey: getSavedSteeringProfileQueryKey(),
        })
      }
    },
  })
  const [pendingAction, setPendingAction] = useState<PendingCurveAction>(null)
  const [lastError, setLastError] = useState<string | null>(null)
  const pendingRef = useRef(false)

  const runAction = async (
    action: Exclude<PendingCurveAction, null>,
    operation: () => Promise<unknown>
  ) => {
    if (pendingRef.current) return
    pendingRef.current = true
    setPendingAction(action)
    setLastError(null)
    try {
      await operation()
    } catch (error) {
      setLastError(
        isApiProblemResponse(error)
          ? error.error.message
          : error instanceof Error
            ? error.message
            : "Unknown steering API error."
      )
    } finally {
      pendingRef.current = false
      setPendingAction(null)
    }
  }

  const save = () => {
    if (!savedProfile) return
    void runAction("save", () =>
      updateProfile({
        path: { profile_id: savedProfile.profile_id },
        body: {
          name: savedProfile.name,
          expected_revision: savedProfile.revision,
          definition: activeCurve.definition,
        },
      })
    )
  }

  const reset = () => {
    if (!savedProfile) return
    void runAction("reset", () =>
      activateProfile({
        body: {
          profile_id: savedProfile.profile_id,
          expected_revision: savedProfile.revision,
        },
      })
    )
  }

  const activeMatchesSaved =
    savedProfile !== null &&
    definitionsEqual(activeCurve.definition, savedProfile.definition)

  return (
    <div className={cn("grid gap-4", className)}>
      <CurveActionError lastError={lastError} />
      <EditorCurveChart
        key={activeCurve.fingerprint}
        activeDefinition={activeCurve.definition}
        speedKph={speedKph}
        activeAssistance={activeAssistance}
        className={chartClassName}
        disabled={!activationAvailable}
        onPointCommit={(definition) =>
          void runAction("apply", () =>
            activateCurve({ body: { definition } })
          )
        }
      />
      <CurveActions
        mode={mode}
        manualAssistanceLevel={manualAssistanceLevel}
        manualAssistanceLevelCount={manualAssistanceLevelCount}
        maximumAssistanceActive={maximumAssistanceActive}
        activeAssistance={activeAssistance}
        pendingAction={pendingAction}
        activeMatchesSaved={activeMatchesSaved}
        hasSavedProfile={savedProfile !== null}
        activationAvailable={activationAvailable}
        modeControlAvailable={modeControlAvailable}
        onModeChange={(nextMode) =>
          void runAction("mode", () => setMode({ body: { mode: nextMode } }))
        }
        onLevelAdjust={(delta) =>
          void runAction("level", () =>
            adjustManualAssistance({ body: { delta } })
          )
        }
        onMaximumChange={(enabled) =>
          void runAction("maximum", () =>
            setMaximumAssistance({ body: { enabled } })
          )
        }
        onSave={save}
        onReset={reset}
      />
    </div>
  )
}
