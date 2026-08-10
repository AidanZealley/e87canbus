import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { buttonProfileErrorDetail } from "./error-detail"

type ButtonProfileErrorProps = {
  title: string
  error: unknown
  actionLabel?: string
  onAction?: () => void
}

export const ButtonProfileError = ({
  title,
  error,
  actionLabel,
  onAction,
}: ButtonProfileErrorProps) => (
  <Alert variant="destructive">
    <AlertTitle>{title}</AlertTitle>
    <AlertDescription className="flex items-center justify-between gap-3">
      <span>{buttonProfileErrorDetail(error)}</span>
      {actionLabel && onAction ? (
        <Button variant="outline" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </AlertDescription>
  </Alert>
)
