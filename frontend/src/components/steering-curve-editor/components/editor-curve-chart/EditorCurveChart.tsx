import { useShallow } from "zustand/react/shallow"

import { CurveChart } from "../curve-chart"
import { useSteeringCurveEditorStore } from "../../store-context"

export const EditorCurveChart = () => {
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
      onPointChange={changePoint}
    />
  )
}
