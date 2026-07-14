import { useState } from "react"
import { useQuery } from "@tanstack/react-query"

import {
  activateSteeringCurve,
  listSteeringProfiles,
  steeringProfilesQueryKey,
  type ActiveSteeringCurve,
  type SteeringCurveDefinition,
} from "@/api/steering"
import { useCarData } from "@/components/car-layout"
import type {
  ApplicationSnapshot,
  SteeringControllerSnapshot,
} from "@/components/simulator-workbench/types"
import { CurveChart } from "@/components/steering-curve-editor/components/curve-chart"
import {
  definitionsEqual,
  replaceAssistanceAt,
} from "@/components/steering-curve-editor/utils"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const NONE_SELECTED = "none-selected"

export const CarSteeringEditor = () => {
  const { application, steeringController } = useCarData()
  const liveActive = application.active_steering_curve
  if (liveActive === null) {
    return (
      <section className="grid min-h-full place-items-center p-4">
        <div className="text-center">
          <h1 className="text-lg font-semibold">Steering</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Active steering curve unavailable.
          </p>
        </div>
      </section>
    )
  }

  return (
    <LoadedSteeringEditor
      application={application}
      steeringController={steeringController}
      initialActive={liveActive}
    />
  )
}

const LoadedSteeringEditor = ({
  application,
  steeringController,
  initialActive,
}: {
  application: ApplicationSnapshot
  steeringController: SteeringControllerSnapshot
  initialActive: ActiveSteeringCurve
}) => {
  const liveActive = application.active_steering_curve ?? initialActive
  const profilesQuery = useQuery({
    queryKey: steeringProfilesQueryKey,
    queryFn: listSteeringProfiles,
  })
  const profiles = profilesQuery.data ?? []
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(
    null
  )
  const [draft, setDraft] = useState<SteeringCurveDefinition>(
    initialActive.definition
  )
  const [draftBase, setDraftBase] = useState<SteeringCurveDefinition>(
    initialActive.definition
  )
  const [acknowledgedActive, setAcknowledgedActive] =
    useState<ActiveSteeringCurve | null>(null)
  const [pending, setPending] = useState(false)
  const [lastError, setLastError] = useState<string | null>(null)
  const [activationMessage, setActivationMessage] = useState<string | null>(
    null
  )
  const [confirmApply, setConfirmApply] = useState(false)
  const [pendingSelection, setPendingSelection] = useState<
    string | null | undefined
  >()

  const active =
    acknowledgedActive !== null &&
    acknowledgedActive.activation_revision > liveActive.activation_revision
      ? acknowledgedActive
      : liveActive

  const selectedProfile =
    profiles.find((profile) => profile.profile_id === selectedProfileId) ?? null
  const dirty = !definitionsEqual(draft, draftBase)
  const draftMatchesActive = definitionsEqual(draft, active.definition)
  const draftMatchesSelected =
    selectedProfile !== null &&
    definitionsEqual(draft, selectedProfile.definition)
  const speedKph = application.speed_valid
    ? application.vehicle_speed_kph
    : null
  const activeAssistance =
    speedKph === null ? null : steeringController.effective_assistance

  const selectAndLoad = (profileId: string | null) => {
    const profile = profiles.find((item) => item.profile_id === profileId)
    setSelectedProfileId(profileId)
    if (profile !== undefined) {
      setDraft(profile.definition)
      setDraftBase(profile.definition)
    }
    setLastError(null)
    setActivationMessage(null)
  }

  const requestSelection = (profileId: string | null) => {
    if (dirty) {
      setPendingSelection(profileId)
      return
    }
    selectAndLoad(profileId)
  }

  const sourceName = draftMatchesSelected ? selectedProfile?.name : undefined
  const apply = async () => {
    if (pending || draftMatchesActive) return
    setPending(true)
    setLastError(null)
    setActivationMessage(null)
    try {
      const response = await activateSteeringCurve(
        draft,
        draftMatchesSelected ? (selectedProfile ?? undefined) : undefined
      )
      setAcknowledgedActive(response)
      setActivationMessage(
        "Draft is active. The saved profile was not changed."
      )
    } catch (error) {
      setLastError(
        error instanceof Error ? error.message : "Activation failed. Try again."
      )
    } finally {
      setPending(false)
      setConfirmApply(false)
    }
  }

  return (
    <section
      className="grid min-h-full grid-rows-[auto_minmax(0,1fr)_auto] gap-2 p-2"
      aria-labelledby="steering-title"
    >
      <div className="flex min-w-0 items-center gap-2">
        <h1 id="steering-title" className="text-lg font-semibold">
          Steering
        </h1>
        <Select
          value={selectedProfileId ?? NONE_SELECTED}
          items={[
            { value: NONE_SELECTED, label: "Choose saved profile" },
            ...profiles.map((profile) => ({
              value: profile.profile_id,
              label: profile.name,
            })),
          ]}
          disabled={pending || profilesQuery.isLoading || profilesQuery.isError}
          onValueChange={(value) =>
            requestSelection(value === NONE_SELECTED ? null : value)
          }
        >
          <SelectTrigger className="min-w-40" aria-label="Saved profile">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE_SELECTED}>Choose saved profile</SelectItem>
            {profiles.map((profile) => (
              <SelectItem key={profile.profile_id} value={profile.profile_id}>
                {profile.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Badge variant="outline">
          {dirty ? "Draft modified" : "Draft unchanged"}
        </Badge>
        {profilesQuery.isError ? (
          <span className="text-xs text-destructive">Profiles unavailable</span>
        ) : null}
        <span className="ml-auto text-xs text-muted-foreground">
          {speedKph === null
            ? "Active position unavailable"
            : `${Math.round(speedKph)} km/h · active ${Math.round((activeAssistance ?? 0) * 100)}%`}
        </span>
      </div>
      <div className="min-h-0 overflow-hidden rounded-lg border bg-card px-2">
        <CurveChart
          active={active.definition}
          draft={draft}
          activeSpeedKph={speedKph}
          activeAssistance={activeAssistance}
          onPointChange={(index, value) => {
            setDraft((current) => replaceAssistanceAt(current, index, value))
            setLastError(null)
            setActivationMessage(null)
          }}
          className="h-full min-h-50 sm:h-full"
        />
      </div>
      <div className="flex min-w-0 items-center gap-2">
        <Button
          variant="outline"
          disabled={pending || !dirty}
          onClick={() => {
            setDraft(draftBase)
            setLastError(null)
            setActivationMessage(null)
          }}
        >
          Revert draft
        </Button>
        <Button
          disabled={pending || draftMatchesActive}
          onClick={() => setConfirmApply(true)}
        >
          {pending ? "Applying…" : "Apply"}
        </Button>
        <p
          className="min-w-0 truncate text-xs text-muted-foreground"
          aria-live="polite"
        >
          {lastError ??
            activationMessage ??
            "Changes remain local until Apply."}
        </p>
      </div>

      <AlertDialog open={confirmApply} onOpenChange={setConfirmApply}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Activate steering draft?</AlertDialogTitle>
            <AlertDialogDescription>
              {sourceName === undefined
                ? "This modified draft will become active without saved-profile provenance."
                : `${sourceName} will become active.`}{" "}
              Applying will not overwrite the saved profile.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
            <AlertDialogAction disabled={pending} onClick={() => void apply()}>
              Confirm activation
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={pendingSelection !== undefined}
        onOpenChange={(open) => {
          if (!open) setPendingSelection(undefined)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Discard draft changes?</AlertDialogTitle>
            <AlertDialogDescription>
              Loading another saved profile will replace the current
              browser-local draft.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep editing</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                selectAndLoad(pendingSelection ?? null)
                setPendingSelection(undefined)
              }}
            >
              Discard and load
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
