import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  activateButtonProfileMutation,
  getSavedButtonProfileOptions,
  getSavedButtonProfileQueryKey,
  updateButtonProfileMutation,
} from "@/api/http/@tanstack/react-query.gen"
import type {
  ApiProblemResponse,
  ButtonProfileDefinitionRequest,
  ButtonProfileResponse,
} from "@/api/http"
import { useLiveStore } from "@/live/live-store"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import { ButtonBindingDialog } from "./ButtonBindingDialog"
import { ButtonProfileGrid } from "./ButtonProfileGrid"
import type { ButtonCommand } from "./types"
import { deriveButtonProfileLedPreview } from "./button-led-presentation"
import {
  buttonProfileStatusLabel,
  isButtonProfileDraftDirty,
  synchronizeButtonProfileDraft,
  type ButtonProfileDraft,
} from "./draft-state"

const errorDetail = (error: unknown): string => {
  if (typeof error === "object" && error !== null) {
    const body = (error as { body?: ApiProblemResponse }).body
    if (body?.error.message) return body.error.message
  }
  return error instanceof Error ? error.message : "The request failed."
}

type ButtonProfileEditorProps = {
  profile?: ButtonProfileResponse
}

export const ButtonProfileEditor = ({
  profile: profileOverride,
}: ButtonProfileEditorProps = {}) => {
  const queryClient = useQueryClient()
  const profileQuery = useQuery(getSavedButtonProfileOptions())
  const savedProfile = profileOverride ?? profileQuery.data
  const liveButtons = useLiveStore((state) => state.buttons)
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const steering = useLiveStore((state) => state.steering)
  const servotronicStatus = useLiveStore(
    (state) => state.devices.registry.servotronic_controller.status
  )
  const steeringFault = useLiveStore((state) => state.health.steering.fault)
  const servotronicFault = useLiveStore(
    (state) =>
      state.health.devices.find(
        (device) => device.role === "servotronic_controller"
      )?.fault ?? null
  )
  const [draft, setDraft] = useState<ButtonProfileDraft | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  const dirty = isButtonProfileDraftDirty(draft)
  const serverChanged =
    savedProfile !== undefined &&
    draft !== null &&
    savedProfile.revision !== draft.sourceRevision

  useEffect(() => {
    const profile = savedProfile
    if (!profile) return
    const synchronizedDraft = synchronizeButtonProfileDraft(
      draft,
      profile.revision,
      profile.definition.slots
    )
    if (synchronizedDraft.draft === draft) return
    // The query result is external state; synchronize only a pristine draft.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDraft(synchronizedDraft.draft)
  }, [draft, savedProfile])
  const slots = draft?.slots ?? null
  const displayRgb = deriveButtonProfileLedPreview(slots ?? [], {
    synchronized,
    steering,
    servotronicUsable:
      synchronized &&
      steering !== null &&
      servotronicStatus === "active" &&
      steeringFault === null &&
      servotronicFault === null,
  })

  const save = useMutation({
    ...updateButtonProfileMutation(),
    onSuccess: (profile) => {
      queryClient.setQueryData(getSavedButtonProfileQueryKey(), profile)
      const savedSlots = [...profile.definition.slots]
      setDraft({
        sourceRevision: profile.revision,
        baseSlots: savedSlots,
        slots: savedSlots,
      })
      toast.success("Button profile saved")
    },
    onError: (error) => toast.error(errorDetail(error)),
  })
  const activate = useMutation({
    ...activateButtonProfileMutation(),
    onSuccess: () => toast.success("Button profile activation requested"),
    onError: (error) => toast.error(errorDetail(error)),
  })

  if (!profileOverride && profileQuery.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Could not load button profile</AlertTitle>
        <AlertDescription className="flex items-center justify-between gap-3">
          <span>{errorDetail(profileQuery.error)}</span>
          <Button variant="outline" onClick={() => profileQuery.refetch()}>
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    )
  }

  if (savedProfile === undefined || slots === null) {
    return (
      <div className="grid min-h-64 place-items-center" role="status">
        <Spinner />
        <span className="sr-only">Loading button profile</span>
      </div>
    )
  }

  const profile = savedProfile
  const isActive =
    synchronized &&
    liveButtons.active_profile_id === profile.profile_id &&
    liveButtons.active_profile_revision === profile.revision
  const isOlderActive =
    synchronized &&
    liveButtons.active_profile_id === profile.profile_id &&
    !isActive
  const applyBinding = (command: ButtonCommand) => {
    if (editingIndex === null) return
    setDraft((current) => {
      if (current === null) return current
      const next = [...current.slots]
      next[editingIndex] = command
      return { ...current, slots: next }
    })
  }

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>{profile.name}</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Click a button to change its command.
          </p>
        </div>
        <Badge variant={isActive ? "default" : "secondary"}>
          {buttonProfileStatusLabel({
            synchronized,
            sameProfile: isActive || isOlderActive,
            sameRevision: isActive,
          })}
        </Badge>
      </CardHeader>
      <CardContent className="grid gap-4">
        <ButtonProfileGrid
          slots={slots}
          rgb={displayRgb}
          onEdit={setEditingIndex}
        />
        <div className="flex flex-wrap justify-end gap-2">
          <Button
            variant="outline"
            disabled={!dirty || serverChanged || save.isPending}
            onClick={() =>
              setDraft({
                sourceRevision: profile.revision,
                baseSlots: [...profile.definition.slots],
                slots: [...profile.definition.slots],
              })
            }
          >
            Discard changes
          </Button>
          <Button
            disabled={!dirty || serverChanged || save.isPending}
            onClick={() =>
              save.mutate({
                path: { profile_id: profile.profile_id },
                body: {
                  name: profile.name,
                  expected_revision: draft?.sourceRevision ?? profile.revision,
                  definition: {
                    schema_version: 1,
                    slots: slots as ButtonProfileDefinitionRequest["slots"],
                  },
                },
              })
            }
          >
            {save.isPending ? "Saving…" : "Save profile"}
          </Button>
          <Button
            variant="secondary"
            disabled={dirty || serverChanged || isActive || activate.isPending}
            onClick={() =>
              activate.mutate({
                body: {
                  profile_id: profile.profile_id,
                  expected_revision: profile.revision,
                },
              })
            }
          >
            {activate.isPending ? "Activating…" : "Activate saved profile"}
          </Button>
        </div>
        {save.isError ? (
          <Alert variant="destructive">
            <AlertTitle>Profile was not saved</AlertTitle>
            <AlertDescription className="flex items-center justify-between gap-3">
              <span>
                {errorDetail(save.error)} Reload the latest saved profile and
                try again.
              </span>
              <Button variant="outline" onClick={() => profileQuery.refetch()}>
                Reload
              </Button>
            </AlertDescription>
          </Alert>
        ) : null}
        {serverChanged && dirty ? (
          <Alert>
            <AlertTitle>Saved profile changed</AlertTitle>
            <AlertDescription className="flex items-center justify-between gap-3">
              <span>
                A newer revision is available. Reloading will discard your
                unsaved button changes.
              </span>
              <Button
                variant="outline"
                onClick={() => {
                  const latestSlots = [...profile.definition.slots]
                  setDraft({
                    sourceRevision: profile.revision,
                    baseSlots: latestSlots,
                    slots: latestSlots,
                  })
                }}
              >
                Reload and discard
              </Button>
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
      {editingIndex !== null ? (
        <ButtonBindingDialog
          key={`${editingIndex}-${JSON.stringify(slots[editingIndex])}`}
          buttonIndex={editingIndex}
          command={slots[editingIndex] ?? null}
          open
          onOpenChange={(open) => {
            if (!open) setEditingIndex(null)
          }}
          onApply={applyBinding}
        />
      ) : null}
    </Card>
  )
}
