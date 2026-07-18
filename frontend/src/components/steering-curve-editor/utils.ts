import type {
  SteeringCurveDefinition,
  SteeringCurvePoint,
} from "@/api/live-contract.gen"

export const ASSISTANCE_INCREMENT_PER_MILLE = 10
export const ASSISTANCE_PAGE_INCREMENT_PER_MILLE = 100

export const speedDeciKphToKph = (value: number) => value / 10
export const assistancePerMilleToPercent = (value: number) => value / 10
export const assistanceToPercent = (value: number) => value * 100
export const assistancePercentToPerMille = (value: number) =>
  Math.round(value * 10)

export const definitionsEqual = (
  left: SteeringCurveDefinition,
  right: SteeringCurveDefinition
) =>
  left.schema_version === right.schema_version &&
  left.points.length === right.points.length &&
  left.points.every(
    (point, index) =>
      point.speed_deci_kph === right.points[index]?.speed_deci_kph &&
      point.assistance_per_mille === right.points[index]?.assistance_per_mille
  )

export const assistanceBoundsAt = (
  definition: SteeringCurveDefinition,
  index: number
) => ({
  minimum: definition.points[index + 1]?.assistance_per_mille ?? 0,
  maximum: definition.points[index - 1]?.assistance_per_mille ?? 1000,
})

export const normalizeAssistanceAt = (
  definition: SteeringCurveDefinition,
  index: number,
  value: number
) => {
  const { minimum, maximum } = assistanceBoundsAt(definition, index)
  const snapped =
    Math.round(value / ASSISTANCE_INCREMENT_PER_MILLE) *
    ASSISTANCE_INCREMENT_PER_MILLE
  return Math.max(
    minimum,
    Math.min(maximum, Math.max(0, Math.min(1000, snapped)))
  )
}

export const replaceAssistanceAt = (
  definition: SteeringCurveDefinition,
  index: number,
  value: number
): SteeringCurveDefinition => ({
  ...definition,
  points: definition.points.map((point, pointIndex) =>
    pointIndex === index
      ? {
          ...point,
          assistance_per_mille: normalizeAssistanceAt(definition, index, value),
        }
      : point
  ) as SteeringCurveDefinition["points"],
})

type CurveForEvaluation = Pick<SteeringCurveDefinition, "schema_version"> & {
  points: readonly SteeringCurvePoint[]
}

export const evaluateSteeringCurve = (
  definition: CurveForEvaluation,
  speedKph: number
) => {
  if (!Number.isFinite(speedKph)) {
    throw new Error("speedKph must be finite")
  }
  return evaluateMonotoneCubicCurve(definition, speedKph)
}

const evaluateMonotoneCubicCurve = (
  definition: CurveForEvaluation,
  speedKph: number
) => {
  const points = definition.points
  if (points.length < 2) {
    throw new Error("monotone-cubic-v1 requires at least two points")
  }
  const x = points.map((point) => point.speed_deci_kph)
  const y = points.map((point) => point.assistance_per_mille / 1000)
  const spans = x.slice(1).map((value, index) => value - (x[index] ?? 0))
  if (spans.some((span) => !Number.isFinite(span) || span <= 0)) {
    throw new Error(
      "monotone-cubic-v1 speeds must be finite and strictly increasing"
    )
  }

  const evaluationX = speedKph * 10
  const firstX = x[0] ?? 0
  const lastX = x.at(-1) ?? firstX
  if (evaluationX <= firstX) return y[0] ?? 0
  if (evaluationX >= lastX) return y.at(-1) ?? 0

  const exactIndex = x.indexOf(evaluationX)
  if (exactIndex >= 0) return y[exactIndex] ?? 0

  const tangents = steffenTangents(x, y)
  for (let index = 0; index < x.length - 1; index += 1) {
    const leftX = x[index] ?? 0
    const rightX = x[index + 1] ?? leftX
    if (evaluationX >= rightX) continue
    const span = rightX - leftX
    const progress = (evaluationX - leftX) / span
    const squared = progress * progress
    const cubed = squared * progress
    const value =
      (2 * cubed - 3 * squared + 1) * (y[index] ?? 0) +
      (cubed - 2 * squared + progress) * span * (tangents[index] ?? 0) +
      (-2 * cubed + 3 * squared) * (y[index + 1] ?? 0) +
      (cubed - squared) * span * (tangents[index + 1] ?? 0)
    return Math.min(1, Math.max(0, value))
  }
  return y.at(-1) ?? 0
}

const steffenTangents = (x: number[], y: number[]) => {
  if (x.length === 2) {
    const secant = ((y[1] ?? 0) - (y[0] ?? 0)) / ((x[1] ?? 0) - (x[0] ?? 0))
    return [secant, secant]
  }
  const interior = x.slice(1, -1).map((_, offset) => {
    const index = offset + 1
    const leftSpan = (x[index] ?? 0) - (x[index - 1] ?? 0)
    const rightSpan = (x[index + 1] ?? 0) - (x[index] ?? 0)
    const leftSecant = ((y[index] ?? 0) - (y[index - 1] ?? 0)) / leftSpan
    const rightSecant = ((y[index + 1] ?? 0) - (y[index] ?? 0)) / rightSpan
    const weightedSecant =
      (leftSecant * rightSpan + rightSecant * leftSpan) / (leftSpan + rightSpan)
    return (
      (d3Sign(leftSecant) + d3Sign(rightSecant)) *
      Math.min(
        Math.abs(leftSecant),
        Math.abs(rightSecant),
        0.5 * Math.abs(weightedSecant)
      )
    )
  })
  const firstSecant = ((y[1] ?? 0) - (y[0] ?? 0)) / ((x[1] ?? 0) - (x[0] ?? 0))
  const lastIndex = x.length - 1
  const lastSecant =
    ((y[lastIndex] ?? 0) - (y[lastIndex - 1] ?? 0)) /
    ((x[lastIndex] ?? 0) - (x[lastIndex - 1] ?? 0))
  return [
    (3 * firstSecant - (interior[0] ?? 0)) / 2,
    ...interior,
    (3 * lastSecant - (interior.at(-1) ?? 0)) / 2,
  ]
}

const d3Sign = (value: number) => (value < 0 ? -1 : 1)

export const sampleSteeringCurve = (
  definition: SteeringCurveDefinition,
  intervalDeciKph = 10
) => {
  if (!Number.isInteger(intervalDeciKph) || intervalDeciKph < 1) {
    throw new Error("sample interval must be a positive integer")
  }
  const first = definition.points[0]
  const last = definition.points.at(-1)
  if (!first || !last) return []
  const speeds = []
  for (
    let speed = first.speed_deci_kph;
    speed < last.speed_deci_kph;
    speed += intervalDeciKph
  ) {
    speeds.push(speed)
  }
  speeds.push(last.speed_deci_kph)
  return speeds.map((speedDeciKph) => ({
    speedKph: speedDeciKph / 10,
    assistance: evaluateSteeringCurve(definition, speedDeciKph / 10),
  }))
}
