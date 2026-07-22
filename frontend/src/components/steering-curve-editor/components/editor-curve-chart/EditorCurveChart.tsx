import type { SteeringCurveDefinition } from "@/api/live-contract.gen"
import { cn } from "@/lib/utils"
import { CurveChart } from "../curve-chart"

type EditorCurveChartProps = {
  activeDefinition: SteeringCurveDefinition
  speedKph: number | null
  activeAssistance: number | null
  className?: string
  disabled?: boolean
  onPointCommit?: (definition: SteeringCurveDefinition) => void
}

export const EditorCurveChart = ({
  activeDefinition,
  speedKph,
  activeAssistance,
  className,
  disabled = false,
  onPointCommit,
}: EditorCurveChartProps) => (
  <CurveChart
    active={activeDefinition}
    draft={activeDefinition}
    activeSpeedKph={speedKph}
    activeAssistance={activeAssistance}
    className={cn(disabled && "opacity-60", className)}
    onPointChange={disabled ? undefined : () => undefined}
    onPointCommit={disabled ? undefined : onPointCommit}
  />
)
