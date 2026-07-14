import type {
  ActiveSteeringCurve,
  SteeringCurveDefinition,
  StoredSteeringProfile,
} from "@/api/steering"
import type { CurveEditorState, CurveEditorStatus } from "./types"

export const ASSISTANCE_INCREMENT_PER_MILLE = 10
export const ASSISTANCE_PAGE_INCREMENT_PER_MILLE = 100

export const speedDeciKphToKph = (value: number) => value / 10
export const assistancePerMilleToPercent = (value: number) => value / 10
export const assistancePercentToPerMille = (value: number) =>
  Math.round(value * 10)

export const definitionsEqual = (
  left: SteeringCurveDefinition,
  right: SteeringCurveDefinition
) =>
  left.schema_version === right.schema_version &&
  left.interpolation === right.interpolation &&
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
  ),
})

export const evaluateLinearCurve = (
  definition: SteeringCurveDefinition,
  speedKph: number
) => {
  const speedDeciKph = speedKph * 10
  const first = definition.points[0]
  const last = definition.points.at(-1)
  if (!first || !last) return 0
  if (speedDeciKph <= first.speed_deci_kph) {
    return first.assistance_per_mille
  }
  if (speedDeciKph >= last.speed_deci_kph) {
    return last.assistance_per_mille
  }

  for (let index = 1; index < definition.points.length; index += 1) {
    const right = definition.points[index]
    const left = definition.points[index - 1]
    if (!left || !right || speedDeciKph > right.speed_deci_kph) continue
    const progress =
      (speedDeciKph - left.speed_deci_kph) /
      (right.speed_deci_kph - left.speed_deci_kph)
    return (
      left.assistance_per_mille +
      progress * (right.assistance_per_mille - left.assistance_per_mille)
    )
  }
  return last.assistance_per_mille
}

export const deriveEditorStatus = (
  state: CurveEditorState,
  savedCatalog: StoredSteeringProfile[]
): CurveEditorStatus => {
  const selectedProfile =
    savedCatalog.find(
      (profile) => profile.profile_id === state.selectedProfileId
    ) ?? null
  return {
    selectedProfile,
    draftMatchesActive: definitionsEqual(state.draft, state.active.definition),
    draftMatchesSelectedSaved:
      selectedProfile !== null &&
      definitionsEqual(state.draft, selectedProfile.definition),
    activeChangedExternally:
      (state.draftBaseActivationRevision !== state.active.activation_revision ||
        state.draftBaseFingerprint !== state.active.fingerprint) &&
      !definitionsEqual(state.draft, state.active.definition),
  }
}

export const reconcileActiveCurve = (
  state: CurveEditorState,
  active: ActiveSteeringCurve
): CurveEditorState => {
  if (
    state.active.activation_revision === active.activation_revision &&
    state.active.fingerprint === active.fingerprint &&
    state.active.status === active.status &&
    state.active.saved_profile_id === active.saved_profile_id &&
    state.active.saved_profile_revision === active.saved_profile_revision &&
    definitionsEqual(state.active.definition, active.definition)
  ) {
    return state
  }
  const draftWasClean = definitionsEqual(state.draft, state.active.definition)
  return {
    ...state,
    active,
    draft: draftWasClean ? active.definition : state.draft,
    draftBaseActivationRevision: draftWasClean
      ? active.activation_revision
      : state.draftBaseActivationRevision,
    draftBaseFingerprint: draftWasClean
      ? active.fingerprint
      : state.draftBaseFingerprint,
  }
}
