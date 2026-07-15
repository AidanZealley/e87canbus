import { useShallow } from "zustand/react/shallow"

import { Button } from "@/components/ui/button"
import { selectStatus } from "../../store"
import { useSteeringCurveEditorStore } from "../../store-context"
import { DeleteSavedButton } from "./components/delete-saved-button/DeleteSavedButton"
import { ReloadActiveButton } from "./components/reload-active-button/ReloadActiveButton"

export const CurveActions = () => {
  const {
    pendingAction,
    applyDraft,
    saveRevision,
    reloadActive,
    deleteSaved,
  } = useSteeringCurveEditorStore(
    useShallow((state) => ({
      pendingAction: state.pendingAction,
      applyDraft: state.applyDraft,
      saveRevision: state.saveRevision,
      reloadActive: state.reloadActive,
      deleteSaved: state.deleteSaved,
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
