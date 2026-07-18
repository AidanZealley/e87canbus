import type {
  CommandAcknowledgement,
  SteeringProfileResponse,
} from "@/api/http/types.gen"
import type {
  ActiveSteeringCurveState,
  SteeringCurveDefinition,
} from "@/api/live-contract.gen"

export type PendingCurveAction = "apply" | "save" | "save-as" | "delete" | null

export type CurveEditorState = {
  active: ActiveSteeringCurveState
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
  selectedProfile: SteeringProfileResponse | null
}

export type SteeringCurveEditorEffects = {
  activate: (
    definition: SteeringCurveDefinition,
    savedProfile?: SteeringProfileResponse
  ) => Promise<CommandAcknowledgement>
  createProfile: (
    name: string,
    definition: SteeringCurveDefinition
  ) => Promise<SteeringProfileResponse>
  updateProfile: (
    profile: SteeringProfileResponse,
    definition: SteeringCurveDefinition
  ) => Promise<SteeringProfileResponse>
  deleteProfile: (profile: SteeringProfileResponse) => Promise<void>
}
