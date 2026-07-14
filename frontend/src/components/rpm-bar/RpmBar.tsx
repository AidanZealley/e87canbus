import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { RpmPresentation } from "@/components/car-layout/car-ui"

const SEGMENT_COUNT = 18

const stageLabel: Record<RpmPresentation["stage"], string> = {
  normal: "Normal",
  stage_1: "Shift stage 1",
  stage_2: "Shift stage 2",
  redline: "Redline",
  unavailable: "Unavailable",
}

export type RpmBarProps = RpmPresentation & {
  redlineRpm: number
  className?: string
}

export const RpmBar = ({
  rpm,
  stage,
  position,
  redlineRpm,
  className,
}: RpmBarProps) => {
  const available = rpm !== null && stage !== "unavailable"
  const activeSegments = available ? Math.ceil(position * SEGMENT_COUNT) : 0

  return (
    <Card size="sm" className={className} aria-label="Engine speed">
      <CardContent className="grid min-w-0 gap-2">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
              Engine speed
            </div>
            <div className="mt-1 flex items-baseline gap-1 text-3xl leading-none font-semibold tabular-nums">
              <span className={cn(!available && "text-muted-foreground")}>
                {available ? rpm : "—"}
              </span>
              {available ? (
                <span className="text-xs font-medium text-muted-foreground">
                  RPM
                </span>
              ) : null}
            </div>
          </div>
          <span
            className={cn(
              "text-xs font-medium",
              stage === "stage_1" && "text-amber-700 dark:text-amber-300",
              (stage === "stage_2" || stage === "redline") &&
                "text-destructive",
              stage === "unavailable" && "text-muted-foreground"
            )}
          >
            {stageLabel[stage]}
          </span>
        </div>
        <div
          className="grid h-4 grid-cols-[repeat(18,minmax(0,1fr))] gap-1"
          role="meter"
          aria-label="RPM position"
          aria-valuemin={0}
          aria-valuemax={redlineRpm}
          aria-valuenow={
            rpm === null ? undefined : Math.min(redlineRpm, Math.max(0, rpm))
          }
          aria-valuetext={
            available ? `${rpm} RPM, ${stageLabel[stage]}` : "Unavailable"
          }
        >
          {Array.from({ length: SEGMENT_COUNT }, (_, index) => (
            <span
              key={index}
              aria-hidden="true"
              className={cn(
                "rounded-sm bg-muted",
                index < activeSegments && "bg-foreground/70",
                index < activeSegments && stage === "stage_1" && "bg-amber-500",
                index < activeSegments &&
                  (stage === "stage_2" || stage === "redline") &&
                  "bg-destructive",
                index < activeSegments &&
                  stage === "redline" &&
                  "ring-1 ring-destructive"
              )}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
