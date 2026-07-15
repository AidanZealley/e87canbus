import { ReferenceDot } from "recharts"

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
    <ReferenceDot
      x={speedKph}
      y={assistancePercent}
      r={7}
      fill="var(--color-background)"
      stroke="var(--color-primary)"
      strokeWidth={3}
      className="pointer-events-none"
      ifOverflow="extendDomain"
    />
  )
}
