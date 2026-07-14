import { useMemo, useState } from "react"
import {
  CartesianGrid,
  Line,
  LineChart,
  XAxis,
  YAxis,
  ZIndexLayer,
  useXAxisScale,
  useYAxisInverseScale,
  useYAxisScale,
} from "recharts"

import type { SteeringCurveDefinition } from "@/api/steering"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import {
  assistanceBoundsAt,
  assistanceToPercent,
  assistancePerMilleToPercent,
  sampleSteeringCurve,
  speedDeciKphToKph,
} from "../../utils"
import { DraggableCurvePoint } from "./DraggableCurvePoint"
import { CurvePositionMarker } from "./CurvePositionMarker"

type CurveChartProps = {
  active: SteeringCurveDefinition
  draft: SteeringCurveDefinition
  activeAssistance?: number | null
  onPointChange: (index: number, value: number) => void
}

const chartConfig = {
  active: { label: "Active", color: "var(--color-chart-3)" },
  draft: { label: "Draft", color: "var(--color-primary)" },
} satisfies ChartConfig

const NON_INTERACTIVE_ACTIVE_DOT = { className: "pointer-events-none" } as const
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
const tooltipWrapperStyle = (isAdjustingPoint: boolean) =>
  ({
    pointerEvents: "none",
    opacity: isAdjustingPoint ? 0 : 1,
    transition: "opacity 150ms ease",
  }) as const

export const CurveChart = ({
  active,
  draft,
  activeAssistance = null,
  onPointChange,
}: CurveChartProps) => {
  const [isAdjustingPoint, setIsAdjustingPoint] = useState(false)
  const data = useMemo(() => {
    const activeSamples = sampleSteeringCurve(active)
    const draftSamples = sampleSteeringCurve(draft)
    const samples = draftSamples.map((sample, index) => ({
      speedKph: sample.speedKph,
      draft: assistanceToPercent(sample.assistance),
      active: assistanceToPercent(
        activeSamples[index]?.assistance ?? sample.assistance
      ),
    }))
    return samples
  }, [active, draft])
  return (
    <ChartContainer
      config={chartConfig}
      className="aspect-auto h-75 min-h-75 w-full sm:h-90"
      role="group"
      aria-label="Steering assistance curve. Solid line is active; dashed line is the editable draft."
    >
      <LineChart data={data} margin={CHART_MARGIN}>
        <CartesianGrid vertical={false} />
        <ChartTooltip
          cursor={false}
          isAnimationActive={false}
          wrapperStyle={tooltipWrapperStyle(isAdjustingPoint)}
          content={
            <ChartTooltipContent
              indicator="line"
              labelFormatter={(_, payload) => {
                const tooltipSpeed = payload[0]?.payload?.speedKph
                return typeof tooltipSpeed === "number"
                  ? `${tooltipSpeed.toFixed(1)} km/h`
                  : null
              }}
              formatter={(value, name) => (
                <div className="flex flex-1 items-center justify-between gap-4">
                  <span className="text-muted-foreground">
                    {name === "active"
                      ? chartConfig.active.label
                      : name === "draft"
                        ? chartConfig.draft.label
                        : name}
                  </span>
                  <span className="font-mono font-medium text-foreground tabular-nums">
                    {Number(value).toFixed(1)}%
                  </span>
                </div>
              )}
            />
          }
        />
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
          dataKey="active"
          type="linear"
          stroke="var(--color-active)"
          strokeWidth={3}
          dot={false}
          activeDot={NON_INTERACTIVE_ACTIVE_DOT}
          isAnimationActive={false}
        />
        <Line
          dataKey="draft"
          type="linear"
          stroke="var(--color-draft)"
          strokeWidth={2}
          strokeDasharray="6 5"
          dot={false}
          activeDot={NON_INTERACTIVE_ACTIVE_DOT}
          isAnimationActive={false}
        />
        <CurvePositionMarker activeAssistance={activeAssistance} />
        <CurvePoints
          definition={draft}
          onPointChange={onPointChange}
          onAdjustingChange={setIsAdjustingPoint}
        />
      </LineChart>
    </ChartContainer>
  )
}

const CurvePoints = ({
  definition,
  onPointChange,
  onAdjustingChange,
}: {
  definition: SteeringCurveDefinition
  onPointChange: (index: number, value: number) => void
  onAdjustingChange: (isAdjusting: boolean) => void
}) => {
  const xScale = useXAxisScale()
  const yScale = useYAxisScale()
  const inverseY = useYAxisInverseScale()
  if (!xScale || !yScale || !inverseY) return null

  return (
    <ZIndexLayer zIndex={1300}>
      <g aria-label="Draft curve points">
        {definition.points.map((point, index) => {
          const speedKph = speedDeciKphToKph(point.speed_deci_kph)
          const x = xScale(speedKph)
          const y = yScale(
            assistancePerMilleToPercent(point.assistance_per_mille)
          )
          const { minimum, maximum } = assistanceBoundsAt(definition, index)
          if (typeof x !== "number" || typeof y !== "number") return null
          return (
            <DraggableCurvePoint
              key={point.speed_deci_kph}
              x={x}
              y={y}
              speedKph={speedKph}
              assistancePerMille={point.assistance_per_mille}
              minimum={minimum}
              maximum={maximum}
              inverseY={(pixelValue) => {
                const percent = inverseY(pixelValue)
                return typeof percent === "number" ? percent * 10 : percent
              }}
              onChange={(value) => onPointChange(index, value)}
              onAdjustingChange={onAdjustingChange}
            />
          )
        })}
      </g>
    </ZIndexLayer>
  )
}
