import { useMemo } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  activateSteeringCurve,
  createSteeringProfile,
  deleteSteeringProfile,
  SteeringApiError,
  steeringProfilesQueryKey,
  steeringProfilesQueryOptions,
  updateSteeringProfile,
  type ActiveSteeringCurve,
  type SteeringCurveDefinition,
  type StoredSteeringProfile,
} from "@/api/steering"
import {
  SteeringCurveEditor,
  type SteeringCurveEditorEffects,
} from "@/components/steering-curve-editor"

type SteeringCurveCardProps = {
  activeCurve: ActiveSteeringCurve
  speedKph: number | null
  activeAssistance?: number | null
}

const EMPTY_PROFILES: StoredSteeringProfile[] = []

export const SteeringCurveCard = ({
  activeCurve,
  speedKph,
  activeAssistance = null,
}: SteeringCurveCardProps) => {
  const queryClient = useQueryClient()
  const profilesQuery = useQuery({
    ...steeringProfilesQueryOptions(),
    retry: false,
  })
  const { mutateAsync: activate } = useMutation({
    mutationFn: ({
      definition,
      savedProfile,
    }: {
      definition: SteeringCurveDefinition
      savedProfile?: StoredSteeringProfile
    }) => activateSteeringCurve(definition, savedProfile),
  })
  const { mutateAsync: createProfile } = useMutation({
    mutationFn: ({
      name,
      definition,
    }: {
      name: string
      definition: SteeringCurveDefinition
    }) => createSteeringProfile(name, definition),
    onSuccess: (saved) => replaceProfileInCatalog(queryClient, saved),
  })
  const { mutateAsync: updateProfile } = useMutation({
    mutationFn: ({
      profile,
      definition,
    }: {
      profile: StoredSteeringProfile
      definition: SteeringCurveDefinition
    }) => updateSteeringProfile(profile, definition),
    onSuccess: (saved) => replaceProfileInCatalog(queryClient, saved),
    onError: (error) => {
      if (
        error instanceof SteeringApiError &&
        error.code === "profile_revision_conflict"
      ) {
        return queryClient.invalidateQueries({
          queryKey: steeringProfilesQueryKey,
        })
      }
    },
  })
  const { mutateAsync: deleteProfile } = useMutation({
    mutationFn: deleteSteeringProfile,
    onSuccess: (_, deleted) => {
      queryClient.setQueryData<StoredSteeringProfile[]>(
        steeringProfilesQueryKey,
        (current = []) =>
          current.filter((profile) => profile.profile_id !== deleted.profile_id)
      )
    },
  })
  const effects = useMemo<SteeringCurveEditorEffects>(
    () => ({
      activate: (definition, savedProfile) =>
        activate({ definition, savedProfile }),
      createProfile: (name, definition) => createProfile({ name, definition }),
      updateProfile: (profile, definition) =>
        updateProfile({ profile, definition }),
      deleteProfile: (profile) => deleteProfile(profile),
    }),
    [activate, createProfile, deleteProfile, updateProfile]
  )

  return (
    <SteeringCurveEditor
      activeCurve={activeCurve}
      profiles={profilesQuery.data ?? EMPTY_PROFILES}
      profilesError={profilesQuery.error}
      effects={effects}
      speedKph={speedKph}
      activeAssistance={activeAssistance}
    />
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
