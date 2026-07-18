import { ReferenceLine } from "recharts"

import { assistanceToPercent } from "../../../../utils"

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
    <ReferenceLine
      y={assistancePercent}
      stroke="var(--color-indigo-500)"
      strokeWidth={2}
      strokeOpacity={0.65}
      className="pointer-events-none"
      ifOverflow="extendDomain"
    />
  )
}
