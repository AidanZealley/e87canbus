import { GitCompareArrowsIcon } from "lucide-react"

import {
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
export const EditorHeader = () => {
  return (
    <CardHeader>
      <CardTitle>Steering assistance curve</CardTitle>
      <CardDescription>
        Settings editor · fixed speed points · smooth assistance · simulation only
      </CardDescription>
      <CardAction>
        <GitCompareArrowsIcon aria-hidden="true" />
      </CardAction>
    </CardHeader>
  )
}
