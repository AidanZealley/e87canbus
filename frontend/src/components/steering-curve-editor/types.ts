import type {
  ActiveSteeringCurve,
  SteeringCurveDefinition,
  StoredSteeringProfile,
} from "@/api/steering"
import type { CommandAcknowledgement } from "@/api/commands"

export type PendingCurveAction = "apply" | "save" | "save-as" | "delete" | null

export type CurveEditorState = {
  active: ActiveSteeringCurve
  draft: SteeringCurveDefinition
  draftBaseActivationRevision: number
  draftBaseFingerprint: string
  selectedProfileId: string | null
  pendingAction: PendingCurveAction
  lastError: string | null
  revisionConflict: boolean
}

export type CurveEditorStatus = {
  draftMatchesActive: boolean
  draftMatchesSelectedSaved: boolean
  activeChangedExternally: boolean
  selectedProfile: StoredSteeringProfile | null
}

export type SteeringCurveEditorEffects = {
  activate: (
    definition: SteeringCurveDefinition,
    savedProfile?: StoredSteeringProfile
  ) => Promise<CommandAcknowledgement>
  createProfile: (
    name: string,
    definition: SteeringCurveDefinition
  ) => Promise<StoredSteeringProfile>
  updateProfile: (
    profile: StoredSteeringProfile,
    definition: SteeringCurveDefinition
  ) => Promise<StoredSteeringProfile>
  deleteProfile: (profile: StoredSteeringProfile) => Promise<void>
}
