import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  XAxis,
  YAxis,
  useXAxisScale,
  useYAxisInverseScale,
  useYAxisScale,
} from "recharts"

import type { SteeringCurveDefinition } from "@/api/steering"
import { ChartContainer, type ChartConfig } from "@/components/ui/chart"
import {
  assistanceBoundsAt,
  assistancePerMilleToPercent,
  evaluateLinearCurve,
  speedDeciKphToKph,
} from "../../utils"
import { DraggableCurvePoint } from "./DraggableCurvePoint"

type CurveChartProps = {
  active: SteeringCurveDefinition
  draft: SteeringCurveDefinition
  speedKph: number | null
  onPointChange: (index: number, value: number) => void
}

const chartConfig = {
  active: { label: "Active", color: "var(--color-chart-3)" },
  draft: { label: "Draft", color: "var(--color-primary)" },
} satisfies ChartConfig

export const CurveChart = ({
  active,
  draft,
  speedKph,
  onPointChange,
}: CurveChartProps) => {
  const data = draft.points.map((point, index) => ({
    speedKph: speedDeciKphToKph(point.speed_deci_kph),
    draft: assistancePerMilleToPercent(point.assistance_per_mille),
    active: assistancePerMilleToPercent(
      active.points[index]?.assistance_per_mille ?? point.assistance_per_mille
    ),
  }))
  const markerSpeed =
    speedKph === null ? null : Math.max(0, Math.min(250, speedKph))

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
        {markerSpeed === null ? null : (
          <ReferenceDot
            x={markerSpeed}
            y={assistancePerMilleToPercent(
              evaluateLinearCurve(active, speedKph ?? markerSpeed)
            )}
            r={5}
            fill="var(--color-active)"
            stroke="var(--color-background)"
            strokeWidth={2}
          />
        )}
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
  )
}
