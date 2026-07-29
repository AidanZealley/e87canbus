import type { RpmPresentation } from "@/components/car-layout/car-ui"
import { cn } from "@/lib/utils"
import type { TachSeverity } from "../../utils"
import {
  deriveTachScale,
  padRpmDigits,
  tachNeedlePosition,
  tachSegmentReached,
  tachSeverityAt,
} from "../../utils"

type ClusterTachometerProps = RpmPresentation & {
  redlineRpm: number
  shiftStage1Rpm: number
}

const stageLabel: Record<RpmPresentation["stage"], string> = {
  normal: "Normal",
  stage_1: "Shift stage 1",
  stage_2: "Shift stage 2",
  redline: "Redline",
  unavailable: "Unavailable",
}

/**
 * The strip is drawn in three tones: plain to the shift stages, amber across
 * them, and the limit colour only over the stretch carrying the redline.
 */
const segmentRuleTone: Record<TachSeverity, string> = {
  normal: "bg-foreground/25",
  warn: "bg-amber-500/40",
  critical: "bg-destructive/40",
}

const reachedSegmentRuleTone: Record<TachSeverity, string> = {
  normal: "bg-foreground",
  warn: "bg-amber-500",
  critical: "bg-destructive",
}

const segmentLabelTone: Record<TachSeverity, string> = {
  normal: "text-foreground",
  warn: "text-amber-500",
  critical: "text-destructive",
}

const staffRuleTone: Record<TachSeverity, string> = {
  normal: "text-foreground/10",
  warn: "text-amber-500/20",
  critical: "text-destructive/20",
}

const washTone: Record<TachSeverity, string> = {
  normal: "text-foreground/30",
  warn: "text-amber-500/45",
  critical: "text-destructive/45",
}

const needleTone: Record<TachSeverity, string> = {
  normal: "bg-foreground",
  warn: "bg-amber-500",
  critical: "bg-destructive",
}

/**
 * A ruled strip rather than a dial: hairline staff rules per thousand, a
 * dot-matrix wash over the swept range, and a single hard needle at the
 * current engine speed.
 */
export const ClusterTachometer = ({
  rpm,
  stage,
  redlineRpm,
  shiftStage1Rpm,
}: ClusterTachometerProps) => {
  const available = rpm !== null && stage !== "unavailable"
  const { ceilingRpm, segments } = deriveTachScale({
    redlineRpm,
    shiftStage1Rpm,
  })
  const position = available ? tachNeedlePosition(rpm, ceilingRpm) : 0
  const hot = stage === "stage_2" || stage === "redline"
  // The needle and the wash behind it take the colour of the stretch they are
  // standing in, so the reading matches the strip it is read against.
  const needleSeverity = available ? tachSeverityAt(rpm, segments) : "normal"
  const { pad, digits } = padRpmDigits(available ? rpm : null, ceilingRpm)

  return (
    <div className="flex items-stretch gap-5">
      <div
        className="relative h-10 min-w-0 flex-1"
        role="meter"
        aria-label="Engine speed"
        aria-valuemin={0}
        aria-valuemax={ceilingRpm}
        aria-valuenow={available ? rpm : undefined}
        aria-valuetext={
          available ? `${rpm} rpm, ${stageLabel[stage]}` : "Unavailable"
        }
      >
        {/* Rule capping the strip, as on the reference cluster. */}
        {/* <span
          aria-hidden="true"
          className="absolute inset-x-0 top-0 h-px bg-foreground"
        /> */}

        {/* The swept range, washed in a fine dot matrix beneath the rules. */}
        <div
          aria-hidden="true"
          className="absolute inset-y-0 left-0 overflow-hidden"
          style={{ width: `${position * 100}%` }}
        >
          <span
            className={cn(
              "absolute top-1 bottom-1 left-0 w-screen",
              "bg-[radial-gradient(currentColor_1px,transparent_1px)] bg-size-[4px_4px]",
              washTone[needleSeverity]
            )}
          />
        </div>

        {/* Gapless on purpose: the segments divide the strip into exact
            eighths so a gridline lands where the needle's percentage puts it.
            A flex gap here would spend width the needle knows nothing about,
            walking the gridlines away from it across the strip. */}
        <div aria-hidden="true" className="absolute inset-0 flex">
          {segments.map(({ startRpm, label, severity }) => {
            // Each rule comes up to full strength as the needle reaches its
            // thousand, so the strip fills in sections behind the needle.
            const reached = available && tachSegmentReached(rpm, startRpm)
            return (
              <div key={startRpm} className="relative flex-1">
                {/* The outer box owns the geometry, this one owns the ink: the
                    break between rules is a margin here, so it never comes out
                    of the width the needle's percentage is measured against. */}
                <div
                  className={cn("relative h-full pt-1", startRpm > 0 && "ml-2")}
                >
                  <span
                    className={cn(
                      "absolute inset-x-0 top-0 h-px motion-safe:transition-colors",
                      segmentRuleTone[severity],
                      reached && "h-0.5",
                      reached && reachedSegmentRuleTone[severity]
                    )}
                  />
                  <span
                    className={cn(
                      "leading-none font-semibold tracking-widest",
                      segmentLabelTone[severity]
                    )}
                  >
                    {label ?? ""}
                  </span>
                  {/* Staff rules ruled across each thousand, masked so they
                      fall away towards the foot of the strip. The mask is a
                      layer of its own rather than part of the gradient drawing
                      the rules, so the falloff and the rule spacing stay
                      independent. */}
                  <span
                    className={cn(
                      "absolute inset-x-0 top-1.5 bottom-1 bg-size-[100%_25%]",
                      "bg-[linear-gradient(to_bottom,currentColor_0_1px,transparent_1px_100%)]",
                      "mask-[linear-gradient(to_bottom,#000,#000_10%,rgba(0,0,0,0.25))]",
                      staffRuleTone[severity]
                    )}
                  />
                </div>
              </div>
            )
          })}
        </div>

        {/* The needle. */}
        {available ? (
          <span
            aria-hidden="true"
            className={cn(
              "absolute top-0 bottom-0 w-0.5 -translate-x-1/2 rounded-full",
              "motion-safe:transition-[left] motion-safe:duration-150 motion-safe:ease-out",
              needleTone[needleSeverity],
              stage === "redline" && "motion-safe:animate-shift-strobe"
            )}
            style={{ left: `${position * 100}%` }}
          />
        ) : null}
      </div>

      {/* The caption hangs off the numeral rather than sitting under it in
          flow, so only the figure's own box decides the readout's height. */}
      <div className="relative shrink-0">
        <span
          className={cn(
            "text-6xl leading-[0.85] font-medium tabular-nums",
            available ? "text-foreground" : "text-muted",
            hot && "text-destructive"
          )}
        >
          {/* Hidden from assistive tech for the same reason as the speed pad:
              it holds the width, and "zero eight five zero" is not a reading. */}
          {pad === "" ? null : (
            <span aria-hidden="true" className="text-muted">
              {pad}
            </span>
          )}
          {digits}
        </span>
        <span className="absolute top-full right-0 text-[0.65rem] font-medium tracking-[0.25em] text-muted-foreground">
          RPM
        </span>
      </div>
    </div>
  )
}
