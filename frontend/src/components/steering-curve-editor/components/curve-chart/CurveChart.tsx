import { useMemo, useRef, useState } from "react"
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"

import type { SteeringCurveDefinition } from "@/api/live-contract.gen"
import { ChartContainer, type ChartConfig } from "@/components/ui/chart"
import {
  assistanceToPercent,
  evaluateSteeringCurve,
  replaceAssistanceAt,
  sampleSteeringCurve,
} from "../../utils"
import { CurvePositionMarker } from "./components/curve-position-marker"
import { CurvePoints } from "./components/curve-points"
import { cn } from "@/lib/utils"

type CurveChartProps = {
  active: SteeringCurveDefinition
  draft: SteeringCurveDefinition
  activeSpeedKph?: number | null
  activeAssistance?: number | null
  className?: string
  onPointChange?: (index: number, value: number) => void
  onPointCommit?: (definition: SteeringCurveDefinition) => void
}

const chartConfig = {
  assistance: { label: "Assistance", color: "white" },
} satisfies ChartConfig

const CHART_MARGIN = { top: 18, right: 18, bottom: 8, left: 0 } as const
const SPEED_DOMAIN = [0, 250] as const
const SPEED_TICKS = [0, 10, 20, 30, 60, 100, 160, 250] as const
const SPEED_AXIS_LABEL = {
  value: "Speed (km/h)",
  position: "insideBottom",
  offset: -4,
} as const
const ASSISTANCE_DOMAIN = [0, 100] as const
const ASSISTANCE_TICKS = [0, 25, 50, 75, 100] as const
const formatSpeedTick = (value: number) => `${value}`
const formatAssistanceTick = (value: number) => `${value}%`
export const CurveChart = ({
  active,
  draft,
  activeSpeedKph = null,
  activeAssistance = null,
  className,
  onPointChange,
  onPointCommit = () => undefined,
}: CurveChartProps) => {
  const [preview, setPreview] = useState(draft)
  const previewRef = useRef(preview)

  const handlePointChange = (index: number, value: number) => {
    const next = replaceAssistanceAt(previewRef.current, index, value)
    previewRef.current = next
    setPreview(next)
    onPointChange?.(index, value)
  }

  const handlePointCommit = () => onPointCommit(previewRef.current)
  const markerSpeedKph = activeSpeedKph ?? 0
  const markerAssistance =
    activeAssistance ?? evaluateSteeringCurve(active, markerSpeedKph)
  const data = useMemo(
    () =>
      sampleSteeringCurve(preview).map((sample) => ({
        speedKph: sample.speedKph,
        assistance: assistanceToPercent(sample.assistance),
      })),
    [preview]
  )
  return (
    <ChartContainer
      config={chartConfig}
      className={cn("aspect-auto h-75 min-h-75 w-full sm:h-90", className)}
      role="group"
      aria-label="Steering assistance curve. Drag the points to edit; changes apply immediately."
    >
      <LineChart data={data} margin={CHART_MARGIN}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="speedKph"
          type="number"
          domain={SPEED_DOMAIN}
          ticks={SPEED_TICKS}
          tickLine={false}
          axisLine={false}
          tickFormatter={formatSpeedTick}
          label={SPEED_AXIS_LABEL}
        />
        <YAxis
          type="number"
          domain={ASSISTANCE_DOMAIN}
          ticks={ASSISTANCE_TICKS}
          tickLine={false}
          axisLine={false}
          tickFormatter={formatAssistanceTick}
          width={42}
        />
        <Line
          dataKey="assistance"
          type="linear"
          stroke="white"
          strokeWidth={2}
          dot={false}
          activeDot={false}
          isAnimationActive={false}
        />
        <CurvePositionMarker
          speedKph={markerSpeedKph}
          activeAssistance={markerAssistance}
        />
        <CurvePoints
          definition={preview}
          onPointChange={handlePointChange}
          onPointCommit={handlePointCommit}
        />
      </LineChart>
    </ChartContainer>
  )
}
