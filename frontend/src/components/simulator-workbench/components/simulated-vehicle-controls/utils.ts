export const SWEEP_INTERVAL_MS = 250
export const SWEEP_PERIOD_MS = 12000

/** Triangle wave in [0, 1]: 0 at the cycle start, 1 at the half-way point. */
export const sweepPhase = (elapsedMs: number, periodMs: number) => {
  const progress = (elapsedMs % periodMs) / periodMs
  return progress <= 0.5 ? progress * 2 : 2 - progress * 2
}

export const sweptValue = (
  minimum: number,
  maximum: number,
  step: number,
  phase: number
) => {
  const offset = (maximum - minimum) * phase
  return minimum + Math.round(offset / step) * step
}
