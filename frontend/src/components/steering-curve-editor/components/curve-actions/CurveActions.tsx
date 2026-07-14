import type { PendingCurveAction } from "../../types"
import type { SteeringCurveInterpolation } from "@/api/steering"
import { Button } from "@/components/ui/button"

type CurveActionsProps = {
  pendingAction: PendingCurveAction
  canApply: boolean
  canSave: boolean
  canRevert: boolean
  canDelete: boolean
  draftInterpolation: SteeringCurveInterpolation
  smoothSupported: boolean
  confirmAction:
    { type: "revert" } | { type: "delete"; profileName: string } | null
  onApply: () => void
  onSave: () => void
  onRequestRevert: () => void
  onRequestDelete: () => void
  onConvertInterpolation: () => void
  onConfirm: () => void
  onCancelConfirm: () => void
}

export const CurveActions = ({
  pendingAction,
  canApply,
  canSave,
  canRevert,
  canDelete,
  draftInterpolation,
  smoothSupported,
  confirmAction,
  onApply,
  onSave,
  onRequestRevert,
  onRequestDelete,
  onConvertInterpolation,
  onConfirm,
  onCancelConfirm,
}: CurveActionsProps) => {
  const pending = pendingAction !== null
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        disabled={!canApply || pending}
        onClick={onApply}
      >
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
      <Button
        variant="outline"
        disabled={!canRevert || pending}
        onClick={onRequestRevert}
      >
        Reload active
      </Button>
      <Button
        variant="destructive"
        disabled={!canDelete || pending}
        onClick={onRequestDelete}
      >
        {pendingAction === "delete" ? "Deleting…" : "Delete saved"}
      </Button>

      {confirmAction === null ? null : (
        <div
          className="flex min-h-11 flex-wrap items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3"
          role="alert"
        >
          <span className="text-xs">
            {confirmAction.type === "revert"
              ? "Discard this draft and reload active values?"
              : `Permanently delete ${confirmAction.profileName}?`}
          </span>
          <Button
            variant="destructive"
            disabled={pending}
            onClick={onConfirm}
          >
            Confirm
          </Button>
          <Button
            variant="ghost"
            disabled={pending}
            onClick={onCancelConfirm}
          >
            Cancel
          </Button>
        </div>
      )}
    </div>
  )
}
