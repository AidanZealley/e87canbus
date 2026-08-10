import type { ComponentProps } from "react"
import type { Button } from "@/components/ui/button"

export type LoadingButtonProps = ComponentProps<typeof Button> & {
  isLoading?: boolean
}
