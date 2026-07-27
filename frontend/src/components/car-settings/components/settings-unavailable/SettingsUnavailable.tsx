import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

type SettingsUnavailableProps = {
  loading: boolean
  error: unknown
  refetching: boolean
  onRetry: () => Promise<void>
}

export const SettingsUnavailable = ({
  loading,
  error,
  refetching,
  onRetry,
}: SettingsUnavailableProps) => (
  <Card size="sm" className="sm:col-span-2">
    <CardContent className="flex min-h-40 flex-col items-center justify-center gap-3 text-center">
      <p className="text-muted-foreground">
        {loading
          ? "Loading current settings…"
          : "Current settings unavailable. Editing is disabled."}
      </p>
      {!loading && error !== null ? (
        <Button
          variant="outline"
          size="lg"
          disabled={refetching}
          onClick={() => void onRetry()}
        >
          {refetching ? "Retrying…" : "Retry settings"}
        </Button>
      ) : null}
    </CardContent>
  </Card>
)
