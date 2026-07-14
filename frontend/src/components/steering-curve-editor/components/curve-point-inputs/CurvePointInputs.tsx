import { useShallow } from "zustand/react/shallow"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useSteeringCurveEditorStore } from "../../store-context"
import {
  ASSISTANCE_PAGE_INCREMENT_PER_MILLE,
  assistanceBoundsAt,
  assistancePerMilleToPercent,
  assistancePercentToPerMille,
  speedDeciKphToKph,
} from "../../utils"

export const CurvePointInputs = () => {
  const { draft, pending, changePoint } = useSteeringCurveEditorStore(
    useShallow((state) => ({
      draft: state.draft,
      pending: state.pendingAction !== null,
      changePoint: state.changePoint,
    }))
  )

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
      {draft.points.map((point, index) => {
        const speedKph = speedDeciKphToKph(point.speed_deci_kph)
        const bounds = assistanceBoundsAt(draft, index)
        return (
          <div key={point.speed_deci_kph} className="grid min-w-0 gap-1">
            <Label htmlFor={`assistance-${point.speed_deci_kph}`}>
              {speedKph} km/h
            </Label>
            <div className="flex items-center gap-1">
              <Input
                id={`assistance-${point.speed_deci_kph}`}
                type="number"
                min={assistancePerMilleToPercent(bounds.minimum)}
                max={assistancePerMilleToPercent(bounds.maximum)}
                step={1}
                value={assistancePerMilleToPercent(point.assistance_per_mille)}
                disabled={pending}
                aria-label={`Assistance at ${speedKph} km/h`}
                onKeyDown={(event) => {
                  if (event.key !== "PageUp" && event.key !== "PageDown") return
                  event.preventDefault()
                  changePoint(
                    index,
                    point.assistance_per_mille +
                      (event.key === "PageUp" ? 1 : -1) *
                        ASSISTANCE_PAGE_INCREMENT_PER_MILLE
                  )
                }}
                onChange={(event) => {
                  const value = Number(event.target.value)
                  if (Number.isFinite(value)) {
                    changePoint(index, assistancePercentToPerMille(value))
                  }
                }}
              />
              <span className="text-muted-foreground" aria-hidden="true">
                %
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
