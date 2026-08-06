import type { LucideIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"

type CoordinatorStatusProps = {
  icon?: LucideIcon
  label: string
  ongoing?: boolean
  tone: "positive" | "caution" | "negative" | "neutral" | "info"
  value: string
}

const badgeAppearance: Record<CoordinatorStatusProps["tone"], string> = {
  positive:
    "bg-success/10 text-success dark:bg-success/20 dark:text-emerald-300",
  caution:
    "bg-amber-500/10 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300",
  negative:
    "bg-destructive/10 text-destructive dark:bg-destructive/20 dark:text-red-300",
  neutral: "bg-muted text-muted-foreground",
  info: "bg-cyan-500/10 text-cyan-700 dark:bg-cyan-500/20 dark:text-cyan-300",
}

export const CoordinatorStatus = ({
  icon: Icon,
  label,
  ongoing = false,
  tone,
  value,
}: CoordinatorStatusProps) => (
  <div className="flex min-w-0 flex-col items-start gap-1">
    <span className="text-[0.6875rem] text-muted-foreground">{label}</span>
    <Badge className={cn("max-w-full", badgeAppearance[tone])}>
      {ongoing ? (
        <Spinner data-icon="inline-start" aria-label={`${value} in progress`} />
      ) : Icon ? (
        <Icon data-icon="inline-start" aria-hidden="true" />
      ) : null}
      <span className="truncate">{value}</span>
    </Badge>
  </div>
)
