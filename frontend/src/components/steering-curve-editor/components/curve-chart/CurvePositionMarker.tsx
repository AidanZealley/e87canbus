import { ReferenceDot, ReferenceLine } from "recharts"

import { assistanceToPercent } from "../../utils"

type CurvePositionMarkerProps = {
  speedKph: number | null
  activeAssistance: number | null
}

export const CurvePositionMarker = ({
  speedKph,
  activeAssistance,
}: CurvePositionMarkerProps) => {
  if (speedKph === null || activeAssistance === null) return null

  const assistancePercent = assistanceToPercent(activeAssistance)

  return (
    <>
      <ReferenceLine
        x={speedKph}
        stroke="var(--color-active)"
        strokeDasharray="3 4"
        strokeOpacity={0.65}
        ifOverflow="extendDomain"
      />
      <ReferenceDot
        x={speedKph}
        y={assistancePercent}
        r={6}
        fill="var(--color-active)"
        stroke="var(--color-background)"
        strokeWidth={3}
        ifOverflow="extendDomain"
        label={{
          value: `${speedKph.toFixed(1)} km/h · ${assistancePercent.toFixed(1)}%`,
          position: "top",
          fill: "var(--color-foreground)",
          fontSize: 11,
        }}
      />
    </>
  )
}
