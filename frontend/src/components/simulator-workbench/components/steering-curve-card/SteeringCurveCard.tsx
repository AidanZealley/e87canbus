import { useMemo } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  activateSteeringCurveMutation,
  activateSteeringProfileMutation,
  createSteeringProfileMutation,
  deleteSteeringProfileMutation,
  getSteeringProfileQueryKey,
  listSteeringProfilesOptions,
  listSteeringProfilesQueryKey,
  updateSteeringProfileMutation,
} from "@/api/http/@tanstack/react-query.gen"
import type { SteeringProfileResponse } from "@/api/http/types.gen"
import { isApiProblemResponse } from "@/api/is-api-problem"
import type { ActiveSteeringCurveState } from "@/api/live-contract.gen"
import {
  SteeringCurveEditor,
  type SteeringCurveEditorEffects,
} from "@/components/steering-curve-editor"

type SteeringCurveCardProps = {
  activeCurve: ActiveSteeringCurveState
  speedKph: number | null
  activeAssistance?: number | null
}

const EMPTY_PROFILES: SteeringProfileResponse[] = []

export const SteeringCurveCard = ({
  activeCurve,
  speedKph,
  activeAssistance = null,
}: SteeringCurveCardProps) => {
  const queryClient = useQueryClient()
  const profilesQuery = useQuery({
    ...listSteeringProfilesOptions(),
    retry: false,
  })
  const { mutateAsync: activateCurve } = useMutation(
    activateSteeringCurveMutation()
  )
  const { mutateAsync: activateProfile } = useMutation(
    activateSteeringProfileMutation()
  )
  const { mutateAsync: createProfile } = useMutation({
    ...createSteeringProfileMutation(),
    onSuccess: (saved) => replaceProfileInCatalog(queryClient, saved),
  })
  const { mutateAsync: updateProfile } = useMutation({
    ...updateSteeringProfileMutation(),
    onSuccess: (saved) => replaceProfileInCatalog(queryClient, saved),
    onError: (error) => {
      if (
        isApiProblemResponse(error) &&
        error.error.code === "profile_revision_conflict"
      ) {
        return queryClient.invalidateQueries({
          queryKey: listSteeringProfilesQueryKey(),
        })
      }
    },
  })
  const { mutateAsync: deleteProfile } = useMutation({
    ...deleteSteeringProfileMutation(),
    onSuccess: (_, deleted) => {
      queryClient.removeQueries({
        queryKey: getSteeringProfileQueryKey({ path: deleted.path }),
        exact: true,
      })
      queryClient.setQueryData<SteeringProfileResponse[]>(
        listSteeringProfilesQueryKey(),
        (current = []) =>
          current.filter(
            (profile) => profile.profile_id !== deleted.path.profile_id
          )
      )
    },
  })
  const effects = useMemo<SteeringCurveEditorEffects>(
    () => ({
      activate: (definition, savedProfile) =>
        savedProfile
          ? activateProfile({
              body: {
                profile_id: savedProfile.profile_id,
                expected_revision: savedProfile.revision,
              },
            })
          : activateCurve({ body: { definition } }),
      createProfile: (name, definition) =>
        createProfile({ body: { name, definition } }),
      updateProfile: (profile, definition) =>
        updateProfile({
          path: { profile_id: profile.profile_id },
          body: {
            name: profile.name,
            expected_revision: profile.revision,
            definition,
          },
        }),
      deleteProfile: (profile) =>
        deleteProfile({
          path: { profile_id: profile.profile_id },
          query: { expected_revision: profile.revision },
        }),
    }),
    [
      activateCurve,
      activateProfile,
      createProfile,
      deleteProfile,
      updateProfile,
    ]
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
  saved: SteeringProfileResponse
) => {
  queryClient.setQueryData(
    getSteeringProfileQueryKey({ path: { profile_id: saved.profile_id } }),
    saved
  )
  queryClient.setQueryData<SteeringProfileResponse[]>(
    listSteeringProfilesQueryKey(),
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
