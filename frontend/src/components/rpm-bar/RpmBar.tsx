import { cn } from "@/lib/utils"
import type { RpmPresentation } from "@/components/car-layout/car-ui"

const SEGMENT_COUNT = 18

export type RpmBarProps = RpmPresentation & {
  redlineRpm: number
}

export const RpmBar = ({ rpm, stage, position, redlineRpm }: RpmBarProps) => {
  const available = rpm !== null && stage !== "unavailable"
  const activeSegments = available ? Math.ceil(position * SEGMENT_COUNT) : 0

  return (
    <div className="flex flex-col gap-16">
      <div
        className="grid h-4 grid-cols-18 gap-1"
        role="meter"
        aria-label="RPM position"
        aria-valuemin={0}
        aria-valuemax={redlineRpm}
        aria-valuenow={
          rpm === null ? undefined : Math.min(redlineRpm, Math.max(0, rpm))
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
                "bg-destructive motion-safe:animate-shift-strobe",
              index < activeSegments &&
                stage === "redline" &&
                "ring-1 ring-destructive"
            )}
            style={{
              height: `${16 + 1.3 ** index * 5}px`,
            }}
          />
        ))}
      </div>
      <div className="flex items-baseline gap-1">
        <span className={cn("text-9xl", !available && "text-muted-foreground")}>
          {available ? rpm : "—"}
        </span>
        {available ? (
          <span className="text-4xl font-semibold text-muted-foreground">
            RPM
          </span>
        ) : null}
      </div>
    </div>
  )
}
