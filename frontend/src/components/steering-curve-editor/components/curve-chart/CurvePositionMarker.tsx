import { ReferenceLine } from "recharts"

import { assistanceToPercent } from "../../utils"

type CurvePositionMarkerProps = {
  activeAssistance: number | null
}

export const CurvePositionMarker = ({
  activeAssistance,
}: CurvePositionMarkerProps) => {
  if (activeAssistance === null) return null

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
