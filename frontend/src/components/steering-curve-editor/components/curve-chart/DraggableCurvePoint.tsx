import { useRef, type KeyboardEvent, type PointerEvent } from "react"

import { ASSISTANCE_PAGE_INCREMENT_PER_MILLE } from "../../utils"

type DraggableCurvePointProps = {
  x: number
  y: number
  speedKph: number
  assistancePerMille: number
  minimum: number
  maximum: number
  inverseY: (pixelValue: number) => unknown
  onChange: (value: number) => void
}

export const DraggableCurvePoint = ({
  x,
  y,
  speedKph,
  assistancePerMille,
  minimum,
  maximum,
  inverseY,
  onChange,
}: DraggableCurvePointProps) => {
  const activePointer = useRef<number | null>(null)

  const finishPointer = (event: PointerEvent<SVGCircleElement>) => {
    if (activePointer.current !== event.pointerId) return
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    activePointer.current = null
  }

  const handlePointerMove = (event: PointerEvent<SVGCircleElement>) => {
    if (activePointer.current !== event.pointerId) return
    const chartY = pointerChartY(event)
    if (chartY === null) return
    const value = inverseY(chartY)
    if (typeof value === "number" && Number.isFinite(value)) {
      onChange(value)
    }
  }

  const handleKeyDown = (event: KeyboardEvent<SVGCircleElement>) => {
    const direction = event.key === "ArrowUp" || event.key === "PageUp" ? 1 : -1
    const amount =
      event.key === "PageUp" || event.key === "PageDown"
        ? ASSISTANCE_PAGE_INCREMENT_PER_MILLE
        : 10
    if (
      event.key !== "ArrowUp" &&
      event.key !== "ArrowDown" &&
      event.key !== "PageUp" &&
      event.key !== "PageDown"
    ) {
      return
    }
    event.preventDefault()
    onChange(assistancePerMille + direction * amount)
  }

  return (
    <g>
      <circle
        cx={x}
        cy={y}
        r={18}
        fill="transparent"
        stroke="transparent"
        strokeWidth={3}
        className="cursor-ns-resize touch-none focus-visible:stroke-ring/60 focus-visible:outline-none"
        role="slider"
        tabIndex={0}
        aria-label={`Assistance at ${speedKph} km/h`}
        aria-valuemin={minimum / 10}
        aria-valuemax={maximum / 10}
        aria-valuenow={assistancePerMille / 10}
        aria-valuetext={`${assistancePerMille / 10}%`}
        onKeyDown={handleKeyDown}
        onPointerDown={(event) => {
          activePointer.current = event.pointerId
          event.currentTarget.setPointerCapture?.(event.pointerId)
          event.preventDefault()
        }}
        onPointerMove={handlePointerMove}
        onPointerUp={finishPointer}
        onPointerCancel={finishPointer}
      />
      <circle
        cx={x}
        cy={y}
        r={6}
        className="pointer-events-none fill-background stroke-primary"
        strokeWidth={3}
        aria-hidden="true"
      />
    </g>
  )
}

const pointerChartY = (event: PointerEvent<SVGCircleElement>) => {
  const svg = event.currentTarget.ownerSVGElement
  if (!svg) return null
  const bounds = svg.getBoundingClientRect()
  const viewBoxHeight = svg.viewBox.baseVal.height || bounds.height
  if (bounds.height <= 0 || viewBoxHeight <= 0) return null
  return ((event.clientY - bounds.top) / bounds.height) * viewBoxHeight
}
