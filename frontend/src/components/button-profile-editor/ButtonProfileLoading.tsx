import { Spinner } from "@/components/ui/spinner"

export const ButtonProfileLoading = () => (
  <div className="grid min-h-64 place-items-center" role="status">
    <Spinner />
    <span className="sr-only">Loading button profile</span>
  </div>
)
