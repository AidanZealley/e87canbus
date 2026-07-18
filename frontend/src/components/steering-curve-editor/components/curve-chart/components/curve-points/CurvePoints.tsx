import { ZIndexLayer, useXAxisScale, useYAxisInverseScale, useYAxisScale } from "recharts"

import type { SteeringCurveDefinition } from "@/api/live-contract.gen"
import {
  assistanceBoundsAt,
  assistancePerMilleToPercent,
  speedDeciKphToKph,
} from "../../../../utils"
import { DraggableCurvePoint } from "../draggable-curve-point"

type CurvePointsProps = {
  definition: SteeringCurveDefinition
  onPointChange: (index: number, value: number) => void
  onPointCommit: () => void
}

export const CurvePoints = ({
  definition,
  onPointChange,
  onPointCommit,
}: CurvePointsProps) => {
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
              onRelease={onPointCommit}
            />
          )
        })}
      </g>
    </ZIndexLayer>
  )
}
