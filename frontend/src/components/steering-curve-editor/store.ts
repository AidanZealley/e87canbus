import { createStore, type StoreApi } from "zustand/vanilla"

import { SteeringApiError } from "@/api/steering"
import type { ActiveSteeringCurve, StoredSteeringProfile } from "@/api/steering"
import type {
  CurveEditorState,
  PendingCurveAction,
  SteeringCurveEditorEffects,
} from "./types"
import {
  convertDraftInterpolation,
  deriveEditorStatus,
  reconcileActiveCurve,
  replaceAssistanceAt,
} from "./utils"

export type SteeringCurveEditorStore = CurveEditorState & {
  profiles: StoredSteeringProfile[]
  profilesError: unknown
  newProfileName: string
  effects: SteeringCurveEditorEffects
  syncActiveCurve: (activeCurve: ActiveSteeringCurve) => void
  syncProfiles: (profiles: StoredSteeringProfile[], error: unknown) => void
  syncEffects: (effects: SteeringCurveEditorEffects) => void
  changePoint: (index: number, value: number) => void
  selectProfile: (profileId: string | null) => void
  setNewProfileName: (name: string) => void
  loadSelected: () => void
  reloadActive: () => void
  convertInterpolation: () => void
  applyDraft: () => Promise<void>
  saveRevision: () => Promise<void>
  saveAs: () => Promise<void>
  deleteSaved: (profile: StoredSteeringProfile) => Promise<void>
}

type Store = StoreApi<SteeringCurveEditorStore>

export const createSteeringCurveEditorStore = ({
  activeCurve,
  profiles,
  profilesError,
  effects,
}: {
  activeCurve: ActiveSteeringCurve
  profiles: StoredSteeringProfile[]
  profilesError: unknown
  effects: SteeringCurveEditorEffects
}): Store =>
  createStore<SteeringCurveEditorStore>()((set, get) => ({
    active: activeCurve,
    draft: activeCurve.definition,
    draftBaseActivationRevision: activeCurve.activation_revision,
    draftBaseFingerprint: activeCurve.fingerprint,
    selectedProfileId: activeCurve.saved_profile_id,
    pendingAction: null,
    lastError: null,
    revisionConflict: false,
    profiles,
    profilesError,
    newProfileName: "",
    effects,

    syncActiveCurve: (nextActive) =>
      set((state) => reconcileActiveCurve(state, nextActive)),
    syncProfiles: (nextProfiles, nextError) =>
      set({ profiles: nextProfiles, profilesError: nextError }),
    syncEffects: (nextEffects) => set({ effects: nextEffects }),

    changePoint: (index, value) => {
      if (get().pendingAction !== null) return
      set((state) => ({
        draft: replaceAssistanceAt(state.draft, index, value),
        lastError: null,
      }))
    },
    selectProfile: (profileId) =>
      set({
        selectedProfileId: profileId,
        revisionConflict: false,
        lastError: null,
      }),
    setNewProfileName: (newProfileName) => set({ newProfileName }),
    loadSelected: () => {
      const state = get()
      if (state.pendingAction !== null) return
      const selected = deriveEditorStatus(state, state.profiles).selectedProfile
      if (!selected) return
      set({
        draft: selected.definition,
        draftBaseActivationRevision: state.active.activation_revision,
        draftBaseFingerprint: state.active.fingerprint,
        lastError: null,
        revisionConflict: false,
      })
    },
    reloadActive: () => {
      const { active } = get()
      set({
        draft: active.definition,
        draftBaseActivationRevision: active.activation_revision,
        draftBaseFingerprint: active.fingerprint,
        lastError: null,
        revisionConflict: false,
      })
    },
    convertInterpolation: () =>
      set((state) => ({
        draft: convertDraftInterpolation(
          state.draft,
          state.draft.interpolation === "linear-v1"
            ? "monotone-cubic-v1"
            : "linear-v1"
        ),
        lastError: null,
      })),

    applyDraft: () =>
      runAction(set, get, "apply", async () => {
        const state = get()
        const status = deriveEditorStatus(state, state.profiles)
        const savedProvenance = status.draftMatchesSelectedSaved
          ? (status.selectedProfile ?? undefined)
          : undefined
        await state.effects.activate(
          state.draft,
          savedProvenance
        )
        set({ lastError: null })
      }),
    saveRevision: () => {
      const state = get()
      const selected = deriveEditorStatus(state, state.profiles).selectedProfile
      if (!selected) return Promise.resolve()
      return runAction(set, get, "save", async () => {
        await get().effects.updateProfile(selected, get().draft)
      })
    },
    saveAs: () => {
      const state = get()
      const name = state.newProfileName.trim()
      if (!name) return Promise.resolve()
      return runAction(set, get, "save-as", async () => {
        const saved = await get().effects.createProfile(name, get().draft)
        set({ selectedProfileId: saved.profile_id, newProfileName: "" })
      })
    },
    deleteSaved: (profile) =>
      runAction(set, get, "delete", async () => {
        await get().effects.deleteProfile(profile)
        set((state) => ({
          selectedProfileId:
            state.selectedProfileId === profile.profile_id
              ? null
              : state.selectedProfileId,
        }))
      }),
  }))

const runAction = async (
  set: Store["setState"],
  get: Store["getState"],
  action: Exclude<PendingCurveAction, null>,
  operation: () => Promise<void>
) => {
  if (get().pendingAction !== null) return
  set({ pendingAction: action, lastError: null, revisionConflict: false })
  try {
    await operation()
  } catch (error) {
    set({
      lastError: errorMessage(error),
      revisionConflict:
        error instanceof SteeringApiError &&
        error.code === "profile_revision_conflict",
    })
  } finally {
    set({ pendingAction: null })
  }
}

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "Unknown steering API error."

export const selectStatus = (state: SteeringCurveEditorStore) =>
  deriveEditorStatus(state, state.profiles)
