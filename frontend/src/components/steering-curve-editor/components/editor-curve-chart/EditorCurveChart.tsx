import type { SteeringCurveDefinition } from "@/api/live-contract.gen"
import { cn } from "@/lib/utils"
import { CurveChart } from "../curve-chart"

type EditorCurveChartProps = {
  activeDefinition: SteeringCurveDefinition
  speedKph: number | null
  activeAssistance: number | null
  className?: string
  onPointCommit?: (definition: SteeringCurveDefinition) => void
}

export const EditorCurveChart = ({
  activeDefinition,
  speedKph,
  activeAssistance,
  className,
  onPointCommit,
}: EditorCurveChartProps) => (
  <CurveChart
    active={activeDefinition}
    draft={activeDefinition}
    activeSpeedKph={speedKph}
    activeAssistance={activeAssistance}
    className={cn(onPointCommit === undefined && "opacity-60", className)}
    onPointChange={onPointCommit === undefined ? undefined : () => undefined}
    onPointCommit={onPointCommit}
  />
)
