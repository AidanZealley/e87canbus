import { useShallow } from "zustand/react/shallow"

import { useSteeringCurveEditorStore } from "../../store-context"
import { assistanceToPercent, evaluateSteeringCurve } from "../../utils"

type CurveSpeedComparisonProps = {
  speedKph: number | null
  activeAssistance: number | null
}

export const CurveSpeedComparison = ({
  speedKph,
  activeAssistance,
}: CurveSpeedComparisonProps) => {
  const { activeDefinition, draft } = useSteeringCurveEditorStore(
    useShallow((state) => ({
      activeDefinition: state.active.definition,
      draft: state.draft,
    }))
  )
  const activeAssistancePercent =
    speedKph === null
      ? null
      : assistanceToPercent(
          activeAssistance ?? evaluateSteeringCurve(activeDefinition, speedKph)
        )
  const draftAssistance =
    speedKph === null
      ? null
      : assistanceToPercent(evaluateSteeringCurve(draft, speedKph))

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-6 bg-chart-3" aria-hidden="true" /> Active
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="w-6 border-t-2 border-dashed border-primary"
            aria-hidden="true"
          />{" "}
          Draft
        </span>
      </div>
      {speedKph === null ? (
        <span>No fresh speed sample</span>
      ) : (
        <span>
          At {speedKph.toFixed(1)} km/h: active{" "}
          {activeAssistancePercent?.toFixed(1)}% · draft preview{" "}
          {draftAssistance?.toFixed(1)}%
        </span>
      )}
    </div>
  )
}
