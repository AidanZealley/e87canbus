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
import { ButtonProfilePad } from "./ButtonProfilePad"
import { buttonProfileErrorDetail } from "./error-detail"
import { toButtonCommandSlots, type ButtonCommand } from "./types"
import { defaultColourForCommand } from "./utils"
import { deriveButtonProfileLedPreview } from "./button-led-presentation"

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
      toast.success("Button binding saved")
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
  const commitBinding = async (index: number, command: ButtonCommand) => {
    const next = [...slots]
    const currentSlot = slots[index]
    next[index] =
      command === null
        ? null
        : {
            command,
            colour: currentSlot?.colour ?? defaultColourForCommand(command),
            // Presentation is not editable yet, so changing only the command must
            // not discard authored values that arrived from another client.
            active_colour: currentSlot?.active_colour ?? null,
            animation: currentSlot?.animation ?? null,
          }
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
    <ButtonProfilePad
      slots={slots}
      rgb={displayRgb}
      disabled={save.isPending}
      onChange={commitBinding}
    />
  )
}
