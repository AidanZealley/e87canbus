import { useEffect } from "react"
import { toast } from "sonner"

export const CurveActionError = ({
  lastError,
}: {
  lastError: string | null
}) => {
  useEffect(() => {
    if (!lastError) return
    toast.error("Curve action failed", {
      id: "steering-curve-action-error",
      description: `${lastError} The active curve was retained.`,
    })
  }, [lastError])

  return null
}
