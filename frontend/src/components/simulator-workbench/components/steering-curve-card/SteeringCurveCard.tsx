import type { ActiveSteeringCurveState, Mode } from "@/api/live-contract.gen"
import { Card, CardContent } from "@/components/ui/card"
import { SteeringCurveEditor } from "@/components/steering-curve-editor"
import { EditorHeader } from "@/components/steering-curve-editor/components/editor-header"

type SteeringCurveCardProps = {
  activeCurve: ActiveSteeringCurveState
  mode: Mode
  manualAssistanceLevel: number
  manualAssistanceLevelCount: number
  maximumAssistanceActive: boolean
  speedKph: number | null
  activeAssistance?: number | null
  activationAvailable?: boolean
  modeControlAvailable?: boolean
}

export const SteeringCurveCard = ({
  activeCurve,
  mode,
  manualAssistanceLevel,
  manualAssistanceLevelCount,
  maximumAssistanceActive,
  speedKph,
  activeAssistance = null,
  activationAvailable = true,
  modeControlAvailable = true,
}: SteeringCurveCardProps) => {
  return (
    <Card className="min-w-0">
      <EditorHeader
        activationStatus={activeCurve.status}
        activationAvailable={activationAvailable}
      />
      <CardContent className="grid gap-4">
        <SteeringCurveEditor
          activeCurve={activeCurve}
          mode={mode}
          manualAssistanceLevel={manualAssistanceLevel}
          manualAssistanceLevelCount={manualAssistanceLevelCount}
          maximumAssistanceActive={maximumAssistanceActive}
          speedKph={speedKph}
          activeAssistance={activeAssistance}
          activationAvailable={activationAvailable}
          modeControlAvailable={modeControlAvailable}
        />
      </CardContent>
    </Card>
  )
}
