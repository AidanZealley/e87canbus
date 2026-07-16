import { useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import type {
  DeviceRegistryEntry,
  SteeringState,
  VehicleState,
} from "@/api/live-events"

import {
  activateSteeringCurve,
  steeringProfilesQueryOptions,
  type ActiveSteeringCurve,
  type SteeringCurveDefinition,
} from "@/api/steering"
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
import { useLiveStore } from "@/live/live-store"

const NONE_SELECTED = "none-selected"

export const CarSteeringEditor = () => {
  const steering = useLiveStore((state) => state.steering)
  const vehicle = useLiveStore((state) => state.vehicle)
  const servotronicRegistry = useLiveStore(
    (state) => state.devices.registry.servotronic_controller
  )
  const connected = useLiveStore((state) => state.connection.synchronized)
  const servotronic = steering?.servotronic ?? null
  const reason = dependencyReason(
    connected,
    servotronicRegistry.status,
    servotronic,
    steering
  )
  if (reason !== null || steering === null || servotronic === null) {
    return (
      <section className="grid min-h-full place-items-center p-4">
        <div className="text-center">
          <h1 className="text-lg font-semibold">Steering</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {reason}
          </p>
        </div>
      </section>
    )
  }

  return (
    <LoadedSteeringEditor
      steering={steering}
      vehicle={vehicle}
      servotronic={servotronic}
      initialActive={steering.active_curve}
    />
  )
}

const LoadedSteeringEditor = ({
  steering,
  vehicle,
  servotronic,
  initialActive,
}: {
  steering: SteeringState
  vehicle: VehicleState
  servotronic: NonNullable<SteeringState["servotronic"]>
  initialActive: ActiveSteeringCurve
}) => {
  const liveActive = steering.active_curve
  const profilesQuery = useQuery(steeringProfilesQueryOptions())
  const profiles = profilesQuery.data ?? []
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(
    initialActive.saved_profile_id
  )
  const [draft, setDraft] = useState<SteeringCurveDefinition>(
    initialActive.definition
  )
  const [draftBase, setDraftBase] = useState<SteeringCurveDefinition>(
    initialActive.definition
  )
  const activation = useMutation({
    mutationFn: ({
      definition,
      savedProfile,
    }: {
      definition: SteeringCurveDefinition
      savedProfile?: Parameters<typeof activateSteeringCurve>[1]
    }) => activateSteeringCurve(definition, savedProfile),
  })
  const [lastError, setLastError] = useState<string | null>(null)
  const [activationMessage, setActivationMessage] = useState<string | null>(
    null
  )
  const [confirmApply, setConfirmApply] = useState(false)
  const [pendingSelection, setPendingSelection] = useState<
    string | null | undefined
  >()

  const active = liveActive

  const selectedProfile =
    profiles.find((profile) => profile.profile_id === selectedProfileId) ?? null
  const dirty = !definitionsEqual(draft, draftBase)
  const draftMatchesActive = definitionsEqual(draft, active.definition)
  const draftMatchesSelected =
    selectedProfile !== null &&
    definitionsEqual(draft, selectedProfile.definition)
  const speedKph = vehicle.speed_valid ? vehicle.speed_kph : null
  const activeAssistance = steering.maximum_assistance_active
      ? 1
      : steering.mode === "manual" || speedKph !== null
      ? servotronic.effective_assistance
      : null

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
    if (activation.isPending || draftMatchesActive) return
    setLastError(null)
    setActivationMessage(null)
    try {
      await activation.mutateAsync({
        definition: draft,
        savedProfile: draftMatchesSelected
          ? (selectedProfile ?? undefined)
          : undefined,
      })
      setActivationMessage(
        "Activation accepted. Live state will confirm the active curve."
      )
    } catch (error) {
      setLastError(
        error instanceof Error ? error.message : "Activation failed. Try again."
      )
    } finally {
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
          disabled={
            activation.isPending ||
            profilesQuery.isLoading ||
            profilesQuery.isError
          }
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
          disabled={activation.isPending || !dirty}
          onClick={() => {
            setDraft(draftBase)
            setLastError(null)
            setActivationMessage(null)
          }}
        >
          Revert draft
        </Button>
        <Button
          disabled={activation.isPending || draftMatchesActive}
          onClick={() => setConfirmApply(true)}
        >
          {activation.isPending ? "Applying…" : "Apply"}
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
            <AlertDialogCancel disabled={activation.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={activation.isPending}
              onClick={() => void apply()}
            >
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

const dependencyReason = (
  synchronized: boolean,
  status: DeviceRegistryEntry["status"],
  servotronic: SteeringState["servotronic"],
  steering: SteeringState | null
) => {
  if (!synchronized || steering === null) return "Live steering state unavailable."
  if (status !== "active") return `servotronic controller is ${status}`
  if (servotronic === null) return "servotronic output adapter is unavailable"
  return null
}
