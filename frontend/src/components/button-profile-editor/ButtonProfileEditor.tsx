import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  getSavedButtonProfileOptions,
  getSavedButtonProfileQueryKey,
  updateButtonProfileMutation,
} from "@/api/http/@tanstack/react-query.gen"
import type { ButtonProfileResponse } from "@/api/http"
import { useLiveStore } from "@/live/live-store"
import { ButtonProfileError } from "./ButtonProfileError"
import { ButtonProfileLoading } from "./ButtonProfileLoading"
import { deriveButtonVisualState } from "./button-led-presentation"
import { ButtonProfileList } from "./components/button-profile-list"
import { buttonProfileErrorDetail } from "./error-detail"
import { toButtonCommandSlots, type ButtonCommandSlot } from "./types"

type ButtonProfileEditorProps = {
  profile?: ButtonProfileResponse
}

export const ButtonProfileEditor = ({
  profile: profileOverride,
}: ButtonProfileEditorProps = {}) => {
  const queryClient = useQueryClient()
  const profileQuery = useQuery(getSavedButtonProfileOptions())
  const savedProfile = profileOverride ?? profileQuery.data
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
  const slots = savedProfile?.definition.slots
  const presentationContext = {
    synchronized,
    steering,
    servotronicUsable:
      synchronized &&
      steering !== null &&
      servotronicStatus === "active" &&
      steeringFault === null &&
      servotronicFault === null,
  }
  const visualStates = (slots ?? []).map((slot) =>
    deriveButtonVisualState(slot, presentationContext)
  )

  const save = useMutation({
    ...updateButtonProfileMutation(),
    onSuccess: (profile) => {
      queryClient.setQueryData(getSavedButtonProfileQueryKey(), profile)
      toast.success("Button saved")
    },
    onError: (error) => toast.error(buttonProfileErrorDetail(error)),
  })
  if (!profileOverride && profileQuery.isError) {
    return (
      <ButtonProfileError
        title="Could not load button profile"
        error={profileQuery.error}
        actionLabel="Retry"
        onAction={() => profileQuery.refetch()}
      />
    )
  }

  if (savedProfile === undefined || slots === undefined) {
    return <ButtonProfileLoading />
  }

  const profile = savedProfile
  const commitSlot = async (index: number, slot: ButtonCommandSlot) => {
    const next = [...slots]
    next[index] = slot
    await save.mutateAsync({
      path: { profile_id: profile.profile_id },
      body: {
        name: profile.name,
        expected_revision: profile.revision,
        definition: {
          schema_version: 2,
          slots: toButtonCommandSlots(next),
        },
      },
    })
  }

  return (
    <ButtonProfileList
      slots={slots}
      visualStates={visualStates}
      disabled={save.isPending}
      onChange={commitSlot}
    />
  )
}
