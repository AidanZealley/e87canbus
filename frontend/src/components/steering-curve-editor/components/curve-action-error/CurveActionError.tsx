import { useShallow } from "zustand/react/shallow"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { useSteeringCurveEditorStore } from "../../store-context"

export const CurveActionError = () => {
  const { lastError, profilesError } = useSteeringCurveEditorStore(
    useShallow((state) => ({
      lastError: state.lastError,
      profilesError: state.profilesError,
    }))
  )
  const error = lastError ?? profilesError
  if (!error) return null

  return (
    <Alert variant="destructive" aria-live="assertive">
      <AlertTitle>Curve action failed</AlertTitle>
      <AlertDescription>
        {errorMessage(error)} The draft has been retained.
      </AlertDescription>
    </Alert>
  )
}

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "Unknown steering API error."
