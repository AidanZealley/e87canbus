export const TACH_SEGMENT_RPM = 1000

/**
 * How hard a stretch of the strip reads: the run up to the shift stages is
 * plain, the shift stages themselves are a caution, and only the stretch
 * carrying the redline is drawn as a limit.
 */
export type TachSeverity = "normal" | "warn" | "critical"

export type TachSegment = {
  /** Engine speed this segment begins at. */
  startRpm: number
  /**
   * Thousands marked at the segment's leading gridline, or null for the
   * segment starting at zero, whose gridline is the edge of the strip.
   */
  label: number | null
  severity: TachSeverity
}

export type TachScale = {
  ceilingRpm: number
  segments: readonly TachSegment[]
}

/**
 * The tachometer is a ruler of whole thousands rather than a bar scaled to the
 * redline, so its gridlines stay put as the shift and redline settings move.
 * The scale runs from zero to the thousand above the redline, which keeps the
 * redline itself inside the strip instead of pinned to its right edge.
 */
export const deriveTachScale = ({
  redlineRpm,
  shiftStage1Rpm,
}: {
  redlineRpm: number
  shiftStage1Rpm: number
}): TachScale => {
  const ceilingRpm = Math.max(
    TACH_SEGMENT_RPM * 2,
    Math.ceil((redlineRpm + 1) / TACH_SEGMENT_RPM) * TACH_SEGMENT_RPM
  )
  const segments = Array.from(
    { length: ceilingRpm / TACH_SEGMENT_RPM },
    (_, index): TachSegment => {
      const startRpm = index * TACH_SEGMENT_RPM
      const endRpm = startRpm + TACH_SEGMENT_RPM
      return {
        startRpm,
        label: index === 0 ? null : index,
        // A segment takes its colour once any part of it is past the threshold,
        // so the warning appears while the needle is still approaching.
        severity:
          endRpm > redlineRpm
            ? "critical"
            : endRpm > shiftStage1Rpm
              ? "warn"
              : "normal",
      }
    }
  )
  return { ceilingRpm, segments }
}

/**
 * The severity of the stretch the needle is standing in, which the needle and
 * the swept wash take so the reading is coloured by where it sits on the strip.
 */
export const tachSeverityAt = (
  rpm: number | null,
  segments: readonly TachSegment[]
): TachSeverity => {
  if (rpm === null) return "normal"
  // Over-range readings stay with the last segment, where the needle clamps.
  const segment = segments.findLast((candidate) => rpm >= candidate.startRpm)
  return segment?.severity ?? "normal"
}

/**
 * Whether the needle has reached a segment, which brings that segment's rule
 * up to full strength. Lighting is cumulative rather than a single travelling
 * highlight, so the lit rules read as a coarse bar trailing the needle.
 */
export const tachSegmentReached = (rpm: number | null, startRpm: number) =>
  rpm !== null && rpm > startRpm

/** Where the needle sits across the whole strip, clamped to it. */
export const tachNeedlePosition = (rpm: number | null, ceilingRpm: number) =>
  rpm === null ? 0 : Math.min(1, Math.max(0, rpm / ceilingRpm))

/** Widest speed the readout has to hold: 300 km/h and 186 mph are both three. */
export const SPEED_DIGIT_COUNT = 3

/**
 * Split a reading into leading zeros and significant digits so a readout holds
 * one width and never shuffles sideways as the value climbs. The pad is drawn
 * muted, leaving the real number the only bright part of the figure.
 */
export const padDigits = (value: number | null, count: number) => {
  if (value === null) return { pad: "", digits: "-".repeat(count) }
  const digits = String(Math.max(0, Math.trunc(value)))
  return {
    pad: "0".repeat(Math.max(0, count - digits.length)),
    digits,
  }
}

export const padSpeedDigits = (value: number | null) =>
  padDigits(value, SPEED_DIGIT_COUNT)

/**
 * The engine speed readout is padded to the widest value its own strip can
 * show, so raising the redline past a thousand widens the readout with it.
 */
export const padRpmDigits = (rpm: number | null, ceilingRpm: number) =>
  padDigits(rpm, String(Math.max(0, Math.trunc(ceilingRpm))).length)
