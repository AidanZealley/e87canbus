import type { PendingCurveAction } from "../../types"
import type {
  SteeringCurveInterpolation,
  StoredSteeringProfile,
} from "@/api/steering"
import { Button } from "@/components/ui/button"
import { DeleteSavedButton } from "./components/delete-saved-button"
import { ReloadActiveButton } from "./components/reload-active-button"

type CurveActionsProps = {
  pendingAction: PendingCurveAction
  canApply: boolean
  canSave: boolean
  canRevert: boolean
  selectedProfile: StoredSteeringProfile | null
  draftInterpolation: SteeringCurveInterpolation
  smoothSupported: boolean
  onApply: () => void
  onSave: () => void
  onConfirmReload: () => void
  onConfirmDelete: (profile: StoredSteeringProfile) => void
  onConvertInterpolation: () => void
}

export const CurveActions = ({
  pendingAction,
  canApply,
  canSave,
  canRevert,
  selectedProfile,
  draftInterpolation,
  smoothSupported,
  onApply,
  onSave,
  onConfirmReload,
  onConfirmDelete,
  onConvertInterpolation,
}: CurveActionsProps) => {
  const pending = pendingAction !== null

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button disabled={!canApply || pending} onClick={onApply}>
        {pendingAction === "apply" ? "Applying…" : "Apply draft"}
      </Button>
      <Button
        variant="secondary"
        disabled={!canSave || pending}
        onClick={onSave}
      >
        {pendingAction === "save" ? "Saving…" : "Save revision"}
      </Button>
      <Button
        variant="outline"
        disabled={
          pending || (draftInterpolation === "linear-v1" && !smoothSupported)
        }
        onClick={onConvertInterpolation}
      >
        {draftInterpolation === "linear-v1"
          ? smoothSupported
            ? "Convert draft to smooth"
            : "Smooth unavailable"
          : "Use linear draft"}
      </Button>
      <ReloadActiveButton
        disabled={!canRevert || pending}
        onConfirm={onConfirmReload}
      />
      <DeleteSavedButton
        profile={selectedProfile}
        pending={pending}
        deleting={pendingAction === "delete"}
        onConfirm={onConfirmDelete}
      />
    </div>
  )
}
