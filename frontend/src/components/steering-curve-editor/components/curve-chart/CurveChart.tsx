import { useMemo } from "react"
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
import { ChartContainer, type ChartConfig } from "@/components/ui/chart"
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
  speedKph?: number | null
  activeAssistance?: number | null
  onPointChange: (index: number, value: number) => void
}

const chartConfig = {
  active: { label: "Active", color: "var(--color-chart-3)" },
  draft: { label: "Draft", color: "var(--color-primary)" },
} satisfies ChartConfig

export const CurveChart = ({
  active,
  draft,
  speedKph = null,
  activeAssistance = null,
  onPointChange,
}: CurveChartProps) => {
  const data = useMemo(() => {
    const activeSamples = sampleSteeringCurve(active)
    const draftSamples = sampleSteeringCurve(draft)
    return draftSamples.map((sample, index) => ({
      speedKph: sample.speedKph,
      draft: assistanceToPercent(sample.assistance),
      active: assistanceToPercent(
        activeSamples[index]?.assistance ?? sample.assistance
      ),
    }))
  }, [active, draft])
  return (
    <ChartContainer
      config={chartConfig}
      className="aspect-auto h-75 min-h-75 w-full sm:h-90"
      role="group"
      aria-label="Steering assistance curve. Solid line is active; dashed line is the editable draft."
    >
      <LineChart
        data={data}
        margin={{ top: 18, right: 18, bottom: 8, left: 0 }}
      >
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="speedKph"
          type="number"
          domain={[0, 250]}
          ticks={[0, 10, 20, 30, 60, 100, 160, 250]}
          tickLine={false}
          axisLine={false}
          tickFormatter={(value: number) => `${value}`}
          label={{
            value: "Speed (km/h)",
            position: "insideBottom",
            offset: -4,
          }}
        />
        <YAxis
          type="number"
          domain={[0, 100]}
          ticks={[0, 25, 50, 75, 100]}
          tickLine={false}
          axisLine={false}
          tickFormatter={(value: number) => `${value}%`}
          width={42}
        />
        <Line
          dataKey="active"
          type="linear"
          stroke="var(--color-active)"
          strokeWidth={3}
          dot={false}
          isAnimationActive={false}
        />
        <Line
          dataKey="draft"
          type="linear"
          stroke="var(--color-draft)"
          strokeWidth={2}
          strokeDasharray="6 5"
          dot={false}
          isAnimationActive={false}
        />
        <CurvePositionMarker
          speedKph={speedKph}
          activeAssistance={activeAssistance}
        />
        <CurvePoints definition={draft} onPointChange={onPointChange} />
      </LineChart>
    </ChartContainer>
  )
}

const CurvePoints = ({
  definition,
  onPointChange,
}: {
  definition: SteeringCurveDefinition
  onPointChange: (index: number, value: number) => void
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
            />
          )
        })}
      </g>
    </ZIndexLayer>
  )
}
