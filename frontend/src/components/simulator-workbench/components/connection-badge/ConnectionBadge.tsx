import { CableIcon, UnplugIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"

type ConnectionBadgeProps = {
  connected: boolean
}

export const ConnectionBadge = ({ connected }: ConnectionBadgeProps) => {
  const Icon = connected ? CableIcon : UnplugIcon

  return (
    <Badge variant={connected ? "secondary" : "destructive"}>
      <Icon data-icon="inline-start" />
      {connected ? "Connected" : "Disconnected"}
    </Badge>
  )
}
