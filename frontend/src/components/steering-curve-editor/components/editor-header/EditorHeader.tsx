import { GitCompareArrowsIcon } from "lucide-react"

import {
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useSteeringCurveEditorStore } from "../../store-context"

export const EditorHeader = () => {
  const interpolation = useSteeringCurveEditorStore(
    (state) => state.draft.interpolation
  )

  return (
    <CardHeader>
      <CardTitle>Steering assistance curve</CardTitle>
      <CardDescription>
        Settings editor · fixed speed points · {interpolation} · simulation only
      </CardDescription>
      <CardAction>
        <GitCompareArrowsIcon aria-hidden="true" />
      </CardAction>
    </CardHeader>
  )
}
