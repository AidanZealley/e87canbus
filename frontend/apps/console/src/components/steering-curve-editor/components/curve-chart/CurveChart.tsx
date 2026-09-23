import { useMemo, useRef, useState } from "react"
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"

import type { SteeringCurveDefinition } from "@e87canbus/coordinator-client/api/http/types.gen"
import { ChartContainer, type ChartConfig } from "@/components/ui/chart"
import {
  assistanceToPercent,
  replaceAssistanceAt,
  sampleSteeringCurve,
} from "../../utils"
import { CurvePoints } from "./components/curve-points"
import { cn } from "@/lib/utils"

type CurveChartProps = {
  draft: SteeringCurveDefinition
  className?: string
  onPointCommit?: (definition: SteeringCurveDefinition) => void
}

const chartConfig = {
  assistance: { label: "Assistance", color: "var(--color-foreground)" },
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
  draft,
  className,
  onPointCommit = () => undefined,
}: CurveChartProps) => {
  const [preview, setPreview] = useState(draft)
  const previewRef = useRef(preview)

  const handlePointChange = (index: number, value: number) => {
    const next = replaceAssistanceAt(previewRef.current, index, value)
    previewRef.current = next
    setPreview(next)
  }

  const handlePointCommit = () => onPointCommit(previewRef.current)
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
      aria-label="Desired steering assistance curve. Drag the points to edit."
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
          stroke="var(--color-assistance)"
          strokeWidth={2}
          dot={false}
          activeDot={false}
          isAnimationActive={false}
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
