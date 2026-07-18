import { LightbulbIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Progress, ProgressLabel } from "@/components/ui/progress"
import { useLiveStore } from "@/live/live-store"

const STROBE_CYCLE_COUNT = 5

export const LightingStatus = () => {
  const synchronized = useLiveStore((state) => state.connection.synchronized)
  const lighting = useLiveStore((state) => state.lighting)
  if (!synchronized) return null

  const requested = lighting.high_beam_enabled
  const observed = lighting.observed_high_beam_enabled
  const active = lighting.high_beam_strobe_active
  const remaining = lighting.high_beam_strobe_cycles_remaining
  const completedCycles = active
    ? Math.max(0, Math.min(STROBE_CYCLE_COUNT, STROBE_CYCLE_COUNT - remaining))
    : 0

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>High-beam strobe</CardTitle>
        <CardDescription>
          Requested controller output and virtual-car observation
        </CardDescription>
        <CardAction>
          <LightbulbIcon aria-hidden="true" />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div
          className="grid grid-cols-2 gap-2"
          role="status"
          aria-live="polite"
        >
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">Requested</div>
            <Badge className="mt-1" variant={requested ? "default" : "outline"}>
              {requested ? "High beam on" : "High beam off"}
            </Badge>
          </div>
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">
              Virtual car observed
            </div>
            <Badge className="mt-1" variant={observed ? "default" : "outline"}>
              {observed === null
                ? "Unavailable"
                : observed
                  ? "High beam on"
                  : "High beam off"}
            </Badge>
          </div>
        </div>
        <Progress
          value={(completedCycles / STROBE_CYCLE_COUNT) * 100}
          aria-label="Completed high-beam strobe cycles"
        >
          <ProgressLabel>
            {completedCycles} / {STROBE_CYCLE_COUNT} cycles complete
          </ProgressLabel>
        </Progress>
        <p className="text-xs text-muted-foreground tabular-nums">
          {active ? `${remaining} cycles remaining` : "Strobe idle"}
        </p>
      </CardContent>
      <CardFooter>
        <p className="text-xs text-muted-foreground">
          Button 4 starts one bounded flash-to-pass sequence.
        </p>
      </CardFooter>
    </Card>
  )
}
