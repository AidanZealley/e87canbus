import { useEffect } from "react"
import { toast } from "sonner"
import { useShallow } from "zustand/react/shallow"

import { useSteeringCurveEditorStore } from "../../store-context"

export const CurveActionError = () => {
  const { lastError, profilesError } = useSteeringCurveEditorStore(
    useShallow((state) => ({
      lastError: state.lastError,
      profilesError: state.profilesError,
    }))
  )

  const error = lastError ?? profilesError

  useEffect(() => {
    if (!error) return

    toast.error("Curve action failed", {
      id: "steering-curve-action-error",
      description: `${error instanceof Error ? error.message : "Unknown steering API error."} The draft has been retained.`,
    })
  }, [error])

  return null
}
