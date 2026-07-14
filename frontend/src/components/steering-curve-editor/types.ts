import type {
  ActiveSteeringCurve,
  SteeringCurveDefinition,
  StoredSteeringProfile,
} from "@/api/steering"

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
