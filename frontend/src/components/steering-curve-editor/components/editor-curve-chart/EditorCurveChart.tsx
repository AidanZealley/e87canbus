import { useShallow } from "zustand/react/shallow"

import { CurveChart } from "../curve-chart"
import { useSteeringCurveEditorStore } from "../../store-context"

type EditorCurveChartProps = {
  speedKph: number | null
  activeAssistance: number | null
}

export const EditorCurveChart = ({
  speedKph,
  activeAssistance,
}: EditorCurveChartProps) => {
  const { activeDefinition, draft, changePoint } = useSteeringCurveEditorStore(
    useShallow((state) => ({
      activeDefinition: state.active.definition,
      draft: state.draft,
      changePoint: state.changePoint,
    }))
  )

  return (
    <CurveChart
      active={activeDefinition}
      draft={draft}
      activeSpeedKph={speedKph}
      activeAssistance={activeAssistance}
      onPointChange={changePoint}
    />
  )
}
