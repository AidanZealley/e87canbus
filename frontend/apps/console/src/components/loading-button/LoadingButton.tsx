import type { LoadingButtonProps } from "./types"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

export const LoadingButton = ({ isLoading, children, disabled, ...props }: LoadingButtonProps) => {
  return (
    <Button className="relative" disabled={disabled || isLoading} {...props}>
      <span className={cn("inline-flex items-center gap-1.5", isLoading && "opacity-0")}>
        {children}
      </span>
      {isLoading && (
        <span className="absolute inset-0 flex items-center justify-center">
          <Spinner />
        </span>
      )}
    </Button>
  )
}
