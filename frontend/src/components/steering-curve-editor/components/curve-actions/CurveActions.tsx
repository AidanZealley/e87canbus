import { useShallow } from "zustand/react/shallow"

import { Button } from "@/components/ui/button"
import { selectStatus } from "../../store"
import { useSteeringCurveEditorStore } from "../../store-context"
import { DeleteSavedButton } from "./components/delete-saved-button"
import { ReloadActiveButton } from "./components/reload-active-button"

export const CurveActions = () => {
  const {
    pendingAction,
    draftInterpolation,
    smoothSupported,
    applyDraft,
    saveRevision,
    reloadActive,
    deleteSaved,
    convertInterpolation,
  } = useSteeringCurveEditorStore(
    useShallow((state) => ({
      pendingAction: state.pendingAction,
      draftInterpolation: state.draft.interpolation,
      smoothSupported:
        state.active.supported_interpolations.includes("monotone-cubic-v1"),
      applyDraft: state.applyDraft,
      saveRevision: state.saveRevision,
      reloadActive: state.reloadActive,
      deleteSaved: state.deleteSaved,
      convertInterpolation: state.convertInterpolation,
    }))
  )
  const status = useSteeringCurveEditorStore(useShallow(selectStatus))
  const pending = pendingAction !== null
  const canApply = !status.draftMatchesActive
  const canSave =
    status.selectedProfile !== null && !status.draftMatchesSelectedSaved
  const canRevert = !status.draftMatchesActive

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button disabled={!canApply || pending} onClick={() => void applyDraft()}>
        {pendingAction === "apply" ? "Applying…" : "Apply draft"}
      </Button>
      <Button
        variant="secondary"
        disabled={!canSave || pending}
        onClick={() => void saveRevision()}
      >
        {pendingAction === "save" ? "Saving…" : "Save revision"}
      </Button>
      <Button
        variant="outline"
        disabled={
          pending || (draftInterpolation === "linear-v1" && !smoothSupported)
        }
        onClick={convertInterpolation}
      >
        {draftInterpolation === "linear-v1"
          ? smoothSupported
            ? "Convert draft to smooth"
            : "Smooth unavailable"
          : "Use linear draft"}
      </Button>
      <ReloadActiveButton
        disabled={!canRevert || pending}
        onConfirm={reloadActive}
      />
      <DeleteSavedButton
        profile={status.selectedProfile}
        pending={pending}
        deleting={pendingAction === "delete"}
        onConfirm={(profile) => void deleteSaved(profile)}
      />
    </div>
  )
}
