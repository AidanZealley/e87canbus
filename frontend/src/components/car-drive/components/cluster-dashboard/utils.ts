export const TACH_SEGMENT_RPM = 1000

export type TachSegment = {
  /** Engine speed this segment begins at. */
  startRpm: number
  /**
   * Thousands marked at the segment's leading gridline, or null for the
   * segment starting at zero, whose gridline is the edge of the strip.
   */
  label: number | null
  /** Whether the segment reaches into shift or redline territory. */
  warn: boolean
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
    (_, index) => {
      const startRpm = index * TACH_SEGMENT_RPM
      return {
        startRpm,
        label: index === 0 ? null : index,
        // A segment reads as hot once any part of it is past the first shift
        // stage, so the warning appears while the needle is still approaching.
        warn: startRpm + TACH_SEGMENT_RPM > shiftStage1Rpm,
      }
    }
  )
  return { ceilingRpm, segments }
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
