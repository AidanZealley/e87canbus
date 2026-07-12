import { Cable, Unplug } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

type Props = {
  connected: boolean
}

export function ConnectionBadge({ connected }: Props) {
  const Icon = connected ? Cable : Unplug
  return (
    <Badge
      className={cn(
        "gap-1.5",
        connected ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-700",
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {connected ? "Connected" : "Disconnected"}
    </Badge>
  )
}
