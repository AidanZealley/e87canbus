import { useShallow } from "zustand/react/shallow"

import { Badge } from "@/components/ui/badge"
import { selectStatus } from "../../store"
import { useSteeringCurveEditorStore } from "../../store-context"

export const CurveStateBadges = () => {
  const {
    draftMatchesActive,
    draftMatchesSelectedSaved,
    activeChangedExternally,
    selectedProfile,
    activeRevision,
    revisionConflict,
  } = useSteeringCurveEditorStore(
    useShallow((state) => ({
      ...selectStatus(state),
      activeRevision: state.active.activation_revision,
      revisionConflict: state.revisionConflict,
    }))
  )

  return (
    <div className="flex flex-wrap gap-2" aria-label="Curve state">
      <Badge variant={draftMatchesActive ? "outline" : "secondary"}>
        {draftMatchesActive ? "Draft matches active" : "Draft changed"}
      </Badge>
      <Badge variant="outline">Active · r{activeRevision}</Badge>
      <Badge variant={draftMatchesSelectedSaved ? "outline" : "secondary"}>
        {selectedProfile === null
          ? "No saved selection"
          : draftMatchesSelectedSaved
            ? `Saved · ${selectedProfile.name} r${selectedProfile.revision}`
            : `Differs from saved · ${selectedProfile.name}`}
      </Badge>
      {activeChangedExternally ? (
        <Badge variant="destructive">Active changed externally</Badge>
      ) : null}
      {revisionConflict ? (
        <Badge variant="destructive">Saved revision conflict</Badge>
      ) : null}
    </div>
  )
}
