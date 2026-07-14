import { useEffect, useMemo, useRef, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { GitCompareArrowsIcon } from "lucide-react"

import {
  activateSteeringCurve,
  createSteeringProfile,
  deleteSteeringProfile,
  listSteeringProfiles,
  SteeringApiError,
  steeringProfilesQueryKey,
  updateSteeringProfile,
  type ActiveSteeringCurve,
  type StoredSteeringProfile,
} from "@/api/steering"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { CurveActions } from "./components/curve-actions"
import { CurveChart } from "./components/curve-chart"
import { ProfileSelector } from "./components/profile-selector"
import type { CurveEditorState, PendingCurveAction } from "./types"
import {
  ASSISTANCE_PAGE_INCREMENT_PER_MILLE,
  assistanceBoundsAt,
  assistancePerMilleToPercent,
  assistancePercentToPerMille,
  deriveEditorStatus,
  evaluateLinearCurve,
  reconcileActiveCurve,
  replaceAssistanceAt,
  speedDeciKphToKph,
} from "./utils"

type SteeringCurveEditorProps = {
  activeCurve: ActiveSteeringCurve
  speedKph: number | null
}

const EMPTY_PROFILES: StoredSteeringProfile[] = []

export const SteeringCurveEditor = ({
  activeCurve,
  speedKph,
}: SteeringCurveEditorProps) => {
  const queryClient = useQueryClient()
  const profilesQuery = useQuery({
    queryKey: steeringProfilesQueryKey,
    queryFn: listSteeringProfiles,
    retry: false,
  })
  const profiles = profilesQuery.data ?? EMPTY_PROFILES
  const [state, setState] = useState<CurveEditorState>(() => ({
    active: activeCurve,
    draft: activeCurve.definition,
    draftBaseActivationRevision: activeCurve.activation_revision,
    draftBaseFingerprint: activeCurve.fingerprint,
    selectedProfileId: activeCurve.saved_profile_id,
    pendingAction: null,
    lastError: null,
    revisionConflict: false,
  }))
  const [newProfileName, setNewProfileName] = useState("")
  const actionInFlight = useRef(false)
  const [confirmAction, setConfirmAction] = useState<
    | { type: "revert" }
    | { type: "delete"; profile: StoredSteeringProfile }
    | null
  >(null)

  useEffect(() => {
    setState((current) => reconcileActiveCurve(current, activeCurve))
  }, [activeCurve])

  const status = useMemo(
    () => deriveEditorStatus(state, profiles),
    [state, profiles]
  )
  const pending = state.pendingAction !== null

  const changePoint = (index: number, value: number) => {
    if (pending) return
    setState((current) => ({
      ...current,
      draft: replaceAssistanceAt(current.draft, index, value),
      lastError: null,
    }))
  }

  const runAction = async (
    action: Exclude<PendingCurveAction, null>,
    operation: () => Promise<void>
  ) => {
    if (actionInFlight.current) return
    actionInFlight.current = true
    setState((current) => ({
      ...current,
      pendingAction: action,
      lastError: null,
      revisionConflict: false,
    }))
    try {
      await operation()
    } catch (error) {
      const conflict =
        error instanceof SteeringApiError &&
        error.code === "profile_revision_conflict"
      setState((current) => ({
        ...current,
        lastError: errorMessage(error),
        revisionConflict: conflict,
      }))
      if (conflict) {
        await queryClient.invalidateQueries({
          queryKey: steeringProfilesQueryKey,
        })
      }
    } finally {
      actionInFlight.current = false
      setState((current) => ({ ...current, pendingAction: null }))
    }
  }

  const applyDraft = () =>
    runAction("apply", async () => {
      const savedProvenance = status.draftMatchesSelectedSaved
        ? (status.selectedProfile ?? undefined)
        : undefined
      const active = await activateSteeringCurve(state.draft, savedProvenance)
      setState((current) => ({
        ...current,
        active,
        draftBaseActivationRevision: active.activation_revision,
        draftBaseFingerprint: active.fingerprint,
        lastError: null,
      }))
    })

  const saveRevision = () => {
    const selectedProfile = status.selectedProfile
    if (!selectedProfile) return
    void runAction("save", async () => {
      const saved = await updateSteeringProfile(selectedProfile, state.draft)
      replaceProfileInCatalog(queryClient, saved)
    })
  }

  const saveAs = () => {
    const name = newProfileName.trim()
    if (!name) return
    void runAction("save-as", async () => {
      const saved = await createSteeringProfile(name, state.draft)
      replaceProfileInCatalog(queryClient, saved)
      setState((current) => ({
        ...current,
        selectedProfileId: saved.profile_id,
      }))
      setNewProfileName("")
    })
  }

  const loadSelected = () => {
    if (!status.selectedProfile || pending) return
    setState((current) => ({
      ...current,
      draft: status.selectedProfile?.definition ?? current.draft,
      draftBaseActivationRevision: current.active.activation_revision,
      draftBaseFingerprint: current.active.fingerprint,
      lastError: null,
      revisionConflict: false,
    }))
  }

  const confirmRequestedAction = () => {
    if (confirmAction?.type === "revert") {
      setState((current) => ({
        ...current,
        draft: current.active.definition,
        draftBaseActivationRevision: current.active.activation_revision,
        draftBaseFingerprint: current.active.fingerprint,
        lastError: null,
        revisionConflict: false,
      }))
      setConfirmAction(null)
      return
    }
    if (confirmAction?.type === "delete") {
      const profile = confirmAction.profile
      void runAction("delete", async () => {
        await deleteSteeringProfile(profile)
        queryClient.setQueryData<StoredSteeringProfile[]>(
          steeringProfilesQueryKey,
          (current = []) =>
            current.filter((item) => item.profile_id !== profile.profile_id)
        )
        setState((current) => ({
          ...current,
          selectedProfileId:
            current.selectedProfileId === profile.profile_id
              ? null
              : current.selectedProfileId,
        }))
        setConfirmAction(null)
      })
    }
  }

  const activeAssistance =
    speedKph === null
      ? null
      : assistancePerMilleToPercent(
          evaluateLinearCurve(state.active.definition, speedKph)
        )
  const draftAssistance =
    speedKph === null
      ? null
      : assistancePerMilleToPercent(evaluateLinearCurve(state.draft, speedKph))

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>Steering assistance curve</CardTitle>
        <CardDescription>
          Settings editor · fixed speed points · linear-v1 simulation only
        </CardDescription>
        <CardAction>
          <GitCompareArrowsIcon aria-hidden="true" />
        </CardAction>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="flex flex-wrap gap-2" aria-label="Curve state">
          <Badge variant={status.draftMatchesActive ? "outline" : "secondary"}>
            {status.draftMatchesActive
              ? "Draft matches active"
              : "Draft changed"}
          </Badge>
          <Badge variant="outline">
            Active · r{state.active.activation_revision}
          </Badge>
          <Badge
            variant={status.draftMatchesSelectedSaved ? "outline" : "secondary"}
          >
            {status.selectedProfile === null
              ? "No saved selection"
              : status.draftMatchesSelectedSaved
                ? `Saved · ${status.selectedProfile.name} r${status.selectedProfile.revision}`
                : `Differs from saved · ${status.selectedProfile.name}`}
          </Badge>
          {status.activeChangedExternally ? (
            <Badge variant="destructive">Active changed externally</Badge>
          ) : null}
          {state.revisionConflict ? (
            <Badge variant="destructive">Saved revision conflict</Badge>
          ) : null}
        </div>

        {state.lastError || profilesQuery.error ? (
          <Alert variant="destructive" aria-live="assertive">
            <AlertTitle>Curve action failed</AlertTitle>
            <AlertDescription>
              {state.lastError ?? errorMessage(profilesQuery.error)} The draft
              has been retained.
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-6 bg-chart-3" aria-hidden="true" />{" "}
              Active
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="w-6 border-t-2 border-dashed border-primary"
                aria-hidden="true"
              />{" "}
              Draft
            </span>
          </div>
          {speedKph === null ? (
            <span>No fresh speed sample · evaluated marker hidden</span>
          ) : (
            <span>
              At {speedKph.toFixed(1)} km/h: active{" "}
              {activeAssistance?.toFixed(1)}% · draft preview{" "}
              {draftAssistance?.toFixed(1)}%
            </span>
          )}
        </div>

        <CurveChart
          active={state.active.definition}
          draft={state.draft}
          speedKph={speedKph}
          onPointChange={changePoint}
        />

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
          {state.draft.points.map((point, index) => {
            const speedKphAtPoint = speedDeciKphToKph(point.speed_deci_kph)
            const bounds = assistanceBoundsAt(state.draft, index)
            return (
              <div
                key={point.speed_deci_kph}
                className="grid gap-1 rounded-md border bg-background p-2 text-xs"
              >
                <Label
                  htmlFor={`assistance-${point.speed_deci_kph}`}
                  className="font-medium"
                >
                  {speedKphAtPoint} km/h
                </Label>
                <span className="relative">
                  <Input
                    id={`assistance-${point.speed_deci_kph}`}
                    type="number"
                    className="h-11 bg-background px-2 pr-6 text-base tabular-nums"
                    min={assistancePerMilleToPercent(bounds.minimum)}
                    max={assistancePerMilleToPercent(bounds.maximum)}
                    step={1}
                    value={assistancePerMilleToPercent(
                      point.assistance_per_mille
                    )}
                    disabled={pending}
                    aria-label={`Assistance at ${speedKphAtPoint} km/h`}
                    onKeyDown={(event) => {
                      if (event.key !== "PageUp" && event.key !== "PageDown")
                        return
                      event.preventDefault()
                      changePoint(
                        index,
                        point.assistance_per_mille +
                          (event.key === "PageUp" ? 1 : -1) *
                            ASSISTANCE_PAGE_INCREMENT_PER_MILLE
                      )
                    }}
                    onChange={(event) => {
                      const value = Number(event.target.value)
                      if (Number.isFinite(value)) {
                        changePoint(index, assistancePercentToPerMille(value))
                      }
                    }}
                  />
                  <span className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 text-muted-foreground">
                    %
                  </span>
                </span>
              </div>
            )
          })}
        </div>

        <ProfileSelector
          profiles={profiles}
          selectedProfileId={state.selectedProfileId}
          newProfileName={newProfileName}
          disabled={pending}
          onSelect={(profileId) => {
            setState((current) => ({
              ...current,
              selectedProfileId: profileId,
              revisionConflict: false,
              lastError: null,
            }))
          }}
          onLoad={loadSelected}
          onNewProfileNameChange={setNewProfileName}
          onSaveAs={saveAs}
        />

        <CurveActions
          pendingAction={state.pendingAction}
          canApply={!status.draftMatchesActive}
          canSave={
            status.selectedProfile !== null && !status.draftMatchesSelectedSaved
          }
          canRevert={!status.draftMatchesActive}
          canDelete={status.selectedProfile !== null}
          confirmAction={
            confirmAction?.type === "delete"
              ? {
                  type: "delete",
                  profileName: confirmAction.profile.name,
                }
              : confirmAction
          }
          onApply={() => void applyDraft()}
          onSave={saveRevision}
          onRequestRevert={() => setConfirmAction({ type: "revert" })}
          onRequestDelete={() => {
            if (status.selectedProfile) {
              setConfirmAction({
                type: "delete",
                profile: status.selectedProfile,
              })
            }
          }}
          onConfirm={confirmRequestedAction}
          onCancelConfirm={() => setConfirmAction(null)}
        />

        <p className="text-xs text-muted-foreground" aria-live="polite">
          Editing changes browser draft state only. Apply changes simulator
          runtime; Save changes SQLite. Neither grants physical steering output
          authority.
        </p>
      </CardContent>
    </Card>
  )
}

const replaceProfileInCatalog = (
  queryClient: ReturnType<typeof useQueryClient>,
  saved: StoredSteeringProfile
) => {
  queryClient.setQueryData<StoredSteeringProfile[]>(
    steeringProfilesQueryKey,
    (current = []) =>
      [
        ...current.filter((profile) => profile.profile_id !== saved.profile_id),
        saved,
      ].sort(
        (left, right) =>
          left.name.localeCompare(right.name, undefined, {
            sensitivity: "base",
          }) || left.profile_id.localeCompare(right.profile_id)
      )
  )
}

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "Unknown steering API error."
