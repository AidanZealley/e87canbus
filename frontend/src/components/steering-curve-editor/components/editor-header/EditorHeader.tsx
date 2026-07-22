import { GitCompareArrowsIcon } from "lucide-react"

import {
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { ActiveSteeringCurveState } from "@/api/live-contract.gen"

export const EditorHeader = ({
  activationStatus,
  activationAvailable,
}: {
  activationStatus: ActiveSteeringCurveState["status"]
  activationAvailable: boolean
}) => {
  return (
    <CardHeader>
      <CardTitle>Steering assistance curve</CardTitle>
      <CardDescription>
        Fixed speed points · smooth assistance · validated controller activation
      </CardDescription>
      <CardAction>
        <div className="flex items-center gap-2">
          <Badge
            variant={
              !activationAvailable || activationStatus === "activation_failed"
                ? "destructive"
                : activationStatus === "active"
                  ? "default"
                  : "secondary"
            }
          >
            {!activationAvailable
              ? "Controller unavailable"
              : activationStatus === "activating"
                ? "Pending"
                : activationStatus === "activation_failed"
                  ? "Rejected"
                  : "Active"}
          </Badge>
          <GitCompareArrowsIcon aria-hidden="true" />
        </div>
      </CardAction>
    </CardHeader>
  )
}
