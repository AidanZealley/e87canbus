import { Gauge, Minus, Plus, RotateCcw, Save } from "lucide-react"

import type { Mode } from "@/api/live-contract.gen"
import { LoadingButton } from "@/components/loading-button"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import type { PendingCurveAction } from "../../types"

export const CurveActions = ({
  mode,
  manualAssistanceLevel,
  manualAssistanceLevelCount,
  maximumAssistanceActive,
  activeAssistance = null,
  pendingAction,
  activeMatchesSaved,
  hasSavedProfile,
  onModeChange,
  onLevelAdjust,
  onMaximumChange,
  onSave,
  onReset,
  activationAvailable = true,
  modeControlAvailable = true,
}: {
  mode: Mode
  manualAssistanceLevel: number
  manualAssistanceLevelCount: number
  maximumAssistanceActive: boolean
  activeAssistance?: number | null
  pendingAction: PendingCurveAction
  activeMatchesSaved: boolean
  hasSavedProfile: boolean
  onModeChange: (mode: Mode) => void
  onLevelAdjust: (delta: -1 | 1) => void
  onMaximumChange: (enabled: boolean) => void
  onSave: () => void
  onReset: () => void
  activationAvailable?: boolean
  modeControlAvailable?: boolean
}) => {
  const canAct = activationAvailable && !activeMatchesSaved && hasSavedProfile
  const assistanceReadout =
    activeAssistance !== null && (mode === "manual" || maximumAssistanceActive)
      ? `${Math.round(activeAssistance * 100)}%`
      : "Manual"

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Switch
          id="auto-assist"
          checked={mode === "auto"}
          disabled={pendingAction !== null || !modeControlAvailable}
          onCheckedChange={(checked) =>
            onModeChange(checked ? "auto" : "manual")
          }
        />
        <Label htmlFor="auto-assist">Auto</Label>
        <div
          className="ml-2 flex items-center gap-1"
          aria-label="Manual assistance controls"
        >
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="Decrease assistance"
            disabled={
              pendingAction !== null ||
              !modeControlAvailable ||
              (mode === "manual" &&
                !maximumAssistanceActive &&
                manualAssistanceLevel === 0)
            }
            onClick={() => onLevelAdjust(-1)}
          >
            <Minus />
          </Button>
          <span className="min-w-20 text-center text-xs text-muted-foreground">
            {assistanceReadout}
          </span>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="Increase assistance"
            disabled={
              pendingAction !== null ||
              !modeControlAvailable ||
              (mode === "manual" &&
                !maximumAssistanceActive &&
                manualAssistanceLevel === manualAssistanceLevelCount - 1)
            }
            onClick={() => onLevelAdjust(1)}
          >
            <Plus />
          </Button>
          <Button
            variant={maximumAssistanceActive ? "default" : "outline"}
            size="sm"
            aria-pressed={maximumAssistanceActive}
            disabled={pendingAction !== null || !modeControlAvailable}
            onClick={() => onMaximumChange(!maximumAssistanceActive)}
          >
            <Gauge />
            Max
          </Button>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <LoadingButton
          variant="outline"
          disabled={!canAct || pendingAction !== null}
          isLoading={pendingAction === "reset"}
          onClick={onReset}
        >
          <RotateCcw />
          Reset
        </LoadingButton>
        <LoadingButton
          disabled={!canAct || pendingAction !== null}
          isLoading={pendingAction === "save"}
          onClick={onSave}
        >
          <Save />
          Save
        </LoadingButton>
      </div>
    </div>
  )
}
