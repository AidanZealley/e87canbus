import type { ActiveSteeringCurve, StoredSteeringProfile } from "@/api/steering"
import { Card, CardContent } from "@/components/ui/card"
import { CurveActionError } from "./components/curve-action-error"
import { CurveActions } from "./components/curve-actions"
import { CurvePointInputs } from "./components/curve-point-inputs"
import { CurveSpeedComparison } from "./components/curve-speed-comparison"
import { CurveStateBadges } from "./components/curve-state-badges"
import { EditorCurveChart } from "./components/editor-curve-chart"
import { EditorHeader } from "./components/editor-header"
import { ProfileSelector } from "./components/profile-selector"
import { SteeringCurveEditorProvider } from "./SteeringCurveEditorProvider"
import type { SteeringCurveEditorEffects } from "./types"

type SteeringCurveEditorProps = {
  activeCurve: ActiveSteeringCurve
  profiles: StoredSteeringProfile[]
  profilesError?: unknown
  effects: SteeringCurveEditorEffects
  speedKph: number | null
  activeAssistance?: number | null
}

export const SteeringCurveEditor = ({
  activeCurve,
  profiles,
  profilesError = null,
  effects,
  speedKph,
  activeAssistance = null,
}: SteeringCurveEditorProps) => (
  <SteeringCurveEditorProvider
    activeCurve={activeCurve}
    profiles={profiles}
    profilesError={profilesError}
    effects={effects}
  >
    <Card className="min-w-0">
      <EditorHeader />
      <CardContent className="grid gap-4">
        <CurveStateBadges />
        <CurveActionError />
        <CurveSpeedComparison
          speedKph={speedKph}
          activeAssistance={activeAssistance}
        />
        <EditorCurveChart
          speedKph={speedKph}
          activeAssistance={activeAssistance}
        />
        <CurvePointInputs />
        <ProfileSelector />
        <CurveActions />
        <p className="text-xs text-muted-foreground" aria-live="polite">
          Editing and interpolation conversion change browser draft state only.
          Save creates a saved revision; Apply consciously activates the draft.
          Neither grants physical steering output authority.
        </p>
      </CardContent>
    </Card>
  </SteeringCurveEditorProvider>
)
