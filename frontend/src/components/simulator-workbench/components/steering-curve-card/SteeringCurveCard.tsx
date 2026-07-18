import type { ActiveSteeringCurveState, Mode } from "@/api/live-contract.gen"
import { Card, CardContent } from "@/components/ui/card"
import { SteeringCurveEditor } from "@/components/steering-curve-editor"
import { EditorHeader } from "@/components/steering-curve-editor/components/editor-header"

type SteeringCurveCardProps = {
  activeCurve: ActiveSteeringCurveState
  mode: Mode
  speedKph: number | null
  activeAssistance?: number | null
}

export const SteeringCurveCard = ({
  activeCurve,
  mode,
  speedKph,
  activeAssistance = null,
}: SteeringCurveCardProps) => {
  return (
    <Card className="min-w-0">
      <EditorHeader />
      <CardContent className="grid gap-4">
        <SteeringCurveEditor
          activeCurve={activeCurve}
          mode={mode}
          speedKph={speedKph}
          activeAssistance={activeAssistance}
        />
      </CardContent>
    </Card>
  )
}
