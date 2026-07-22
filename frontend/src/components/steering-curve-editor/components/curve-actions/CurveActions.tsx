import { RotateCcw, Save } from "lucide-react"

import type { Mode } from "@/api/live-contract.gen"
import { LoadingButton } from "@/components/loading-button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import type { PendingCurveAction } from "../../types"

export const CurveActions = ({
  mode,
  pendingAction,
  activeMatchesSaved,
  hasSavedProfile,
  onModeChange,
  onSave,
  onReset,
  activationAvailable = true,
  modeControlAvailable = true,
}: {
  mode: Mode
  pendingAction: PendingCurveAction
  activeMatchesSaved: boolean
  hasSavedProfile: boolean
  onModeChange: (mode: Mode) => void
  onSave: () => void
  onReset: () => void
  activationAvailable?: boolean
  modeControlAvailable?: boolean
}) => {
  const canAct = activationAvailable && !activeMatchesSaved && hasSavedProfile

  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        <Switch
          id="auto-assist"
          checked={mode === "auto"}
          disabled={pendingAction !== null || !modeControlAvailable}
          onCheckedChange={(checked) =>
            onModeChange(checked ? "auto" : "manual")
          }
        />
        <Label htmlFor="auto-assist">Auto</Label>
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
