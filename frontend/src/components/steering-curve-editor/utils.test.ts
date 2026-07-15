import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

import type {
  ActiveSteeringCurve,
  SteeringCurveDefinition,
} from "../../api/steering.ts"
import type { CurveEditorState } from "./types.ts"
import {
  assistanceBoundsAt,
  assistancePercentToPerMille,
  assistancePerMilleToPercent,
  definitionsEqual,
  deriveEditorStatus,
  evaluateSteeringCurve,
  normalizeAssistanceAt,
  reconcileActiveCurve,
  replaceAssistanceAt,
  sampleSteeringCurve,
  speedDeciKphToKph,
} from "./utils.ts"

const definition = (
  values = [1000, 890, 780, 670, 380, 0, 0, 0]
): SteeringCurveDefinition => ({
  schema_version: 1,
  points: [0, 100, 200, 300, 600, 1000, 1600, 2500].map(
    (speed_deci_kph, index) => ({
      speed_deci_kph,
      assistance_per_mille: values[index] ?? 0,
    })
  ),
})

const active = (
  value = definition(),
  activationRevision = 1
): ActiveSteeringCurve => ({
  definition: value,
  fingerprint: `fingerprint-${activationRevision}`,
  activation_revision: activationRevision,
  status: "active",
  saved_profile_id: null,
  saved_profile_revision: null,
})

test("integer units convert to display units without changing authority", () => {
  assert.equal(speedDeciKphToKph(123), 12.3)
  assert.equal(assistancePerMilleToPercent(889), 88.9)
  assert.equal(assistancePercentToPerMille(88.9), 889)
})

test("snap and monotonic neighbor bounds constrain one point", () => {
  const value = definition()
  assert.deepEqual(assistanceBoundsAt(value, 2), { minimum: 670, maximum: 890 })
  assert.equal(normalizeAssistanceAt(value, 2, 886), 890)
  assert.equal(normalizeAssistanceAt(value, 2, 200), 670)

  const changed = replaceAssistanceAt(value, 2, 810)
  assert.deepEqual(
    changed.points.map((point) => point.speed_deci_kph),
    value.points.map((point) => point.speed_deci_kph)
  )
  assert.equal(changed.points[2]?.assistance_per_mille, 810)
  assert.equal(changed.points[1], value.points[1])
  assert.equal(changed.points[3], value.points[3])
})

test("definition equality and dirty state compare complete integer definitions", () => {
  const first = definition()
  const draft = replaceAssistanceAt(first, 2, 810)
  const state: CurveEditorState = {
    active: active(first),
    draft,
    draftBaseActivationRevision: 1,
    draftBaseFingerprint: "fingerprint-1",
    selectedProfileId: "profile",
    pendingAction: null,
    lastError: null,
    revisionConflict: false,
  }
  const saved = {
    profile_id: "profile",
    name: "Track",
    revision: 1,
    definition: draft,
    created_at: "",
    updated_at: "",
  }

  assert.equal(definitionsEqual(first, definition()), true)
  assert.equal(definitionsEqual(first, draft), false)
  assert.deepEqual(deriveEditorStatus(state, [saved]), {
    draftMatchesActive: false,
    draftMatchesSelectedSaved: true,
    activeChangedExternally: false,
    selectedProfile: saved,
  })
})

test("smooth evaluation holds endpoints and uses the selected definition", () => {
  const activeDefinition = definition()
  const draftDefinition = replaceAssistanceAt(activeDefinition, 1, 800)
  assert.equal(evaluateSteeringCurve(activeDefinition, -5), 1)
  assert.ok(Math.abs(evaluateSteeringCurve(activeDefinition, 5) - 0.945) < 1e-12)
  assert.equal(evaluateSteeringCurve(activeDefinition, 300), 0)
  assert.equal(evaluateSteeringCurve(activeDefinition, 10), 0.89)
  assert.equal(evaluateSteeringCurve(draftDefinition, 10), 0.8)
})

type ConformanceVectors = {
  algorithm: "monotone-cubic-v1"
  absolute_tolerance: number
  speeds_deci_kph: number[]
  cases: Array<{
    name: string
    assistance_per_mille: number[]
    evaluations: Array<[number, number]>
  }>
}

test("monotone cubic matches the shared language-neutral golden vectors", () => {
  const vectors = JSON.parse(
    readFileSync(
      new URL(
        "../../../../docs/assist-curve/monotone-cubic-v1-vectors.json",
        import.meta.url
      ),
      "utf8"
    )
  ) as ConformanceVectors

  assert.equal(vectors.algorithm, "monotone-cubic-v1")
  for (const vector of vectors.cases) {
    const value: SteeringCurveDefinition = {
      schema_version: 1,
      points: vectors.speeds_deci_kph.map((speed_deci_kph, index) => ({
        speed_deci_kph,
        assistance_per_mille: vector.assistance_per_mille[index] ?? 0,
      })),
    }
    for (const [speedDeciKph, expected] of vector.evaluations) {
      const actual = evaluateSteeringCurve(value, speedDeciKph / 10)
      assert.ok(
        Math.abs(actual - expected) <= vectors.absolute_tolerance,
        `${vector.name} at ${speedDeciKph} deci-km/h`
      )
    }
  }
})

test("smooth evaluation is bounded, monotone and exactly reproduces points", () => {
  const smooth = definition([1000, 800, 800, 500, 500, 200, 200, 0])
  const samples = Array.from({ length: 2501 }, (_, speed) =>
    evaluateSteeringCurve(smooth, speed / 10)
  )

  assert.ok(
    samples.every((value) => Number.isFinite(value) && value >= 0 && value <= 1)
  )
  assert.ok(
    samples
      .slice(1)
      .every((value, index) => value <= (samples[index] ?? 0) + 1e-12)
  )
  for (const point of smooth.points) {
    assert.equal(
      evaluateSteeringCurve(smooth, point.speed_deci_kph / 10),
      point.assistance_per_mille / 1000
    )
  }
})

test("chart sampling evaluates a bounded deterministic one-km/h grid", () => {
  const smooth = definition()
  const samples = sampleSteeringCurve(smooth)

  assert.equal(samples.length, 251)
  assert.deepEqual(samples[0], { speedKph: 0, assistance: 1 })
  assert.deepEqual(samples.at(-1), { speedKph: 250, assistance: 0 })
  assert.equal(samples[45]?.assistance, evaluateSteeringCurve(smooth, 45))
})

test("invalid evaluation inputs fail closed", () => {
  assert.throws(() => evaluateSteeringCurve(definition(), Number.NaN), /finite/)
})

test("two-point monotone cubic reduces exactly to its secant line", () => {
  const value: SteeringCurveDefinition = {
    schema_version: 1,
    points: [
      { speed_deci_kph: 30, assistance_per_mille: 900 },
      { speed_deci_kph: 770, assistance_per_mille: 100 },
    ],
  }

  assert.equal(evaluateSteeringCurve(value, 3), 0.9)
  assert.equal(evaluateSteeringCurve(value, 40), 0.5)
  assert.equal(evaluateSteeringCurve(value, 77), 0.1)
})

test("defensive smooth evaluator handles unequal spans and rejects non-positive spans", () => {
  const value: SteeringCurveDefinition = {
    schema_version: 1,
    points: [
      { speed_deci_kph: 0, assistance_per_mille: 1000 },
      { speed_deci_kph: 1, assistance_per_mille: 900 },
      { speed_deci_kph: 1_000_001, assistance_per_mille: 100 },
      { speed_deci_kph: 1_000_002, assistance_per_mille: 0 },
    ],
  }
  const evaluationSpeedsDeciKph = [
    0, 0.5, 1, 10, 100_001, 500_001, 900_001, 1_000_001, 1_000_001.5, 1_000_002,
  ]
  const values = evaluationSpeedsDeciKph.map((speed) =>
    evaluateSteeringCurve(value, speed / 10)
  )

  assert.ok(
    values.every(
      (assistance) =>
        Number.isFinite(assistance) && assistance >= 0 && assistance <= 1
    )
  )
  assert.ok(
    values
      .slice(1)
      .every((assistance, index) => assistance <= (values[index] ?? 0) + 1e-12)
  )
  for (const point of value.points) {
    assert.equal(
      evaluateSteeringCurve(value, point.speed_deci_kph / 10),
      point.assistance_per_mille / 1000
    )
  }

  for (const points of [
    [
      { speed_deci_kph: 0, assistance_per_mille: 1000 },
      { speed_deci_kph: 0, assistance_per_mille: 0 },
    ],
    [
      { speed_deci_kph: 1, assistance_per_mille: 1000 },
      { speed_deci_kph: 0, assistance_per_mille: 0 },
    ],
  ]) {
    assert.throws(
      () => evaluateSteeringCurve({ ...value, points }, 0),
      /strictly increasing/
    )
  }
})

test("an external active change preserves dirty drafts but advances clean drafts", () => {
  const initial = active()
  const dirty = replaceAssistanceAt(initial.definition, 2, 810)
  const state: CurveEditorState = {
    active: initial,
    draft: dirty,
    draftBaseActivationRevision: 1,
    draftBaseFingerprint: initial.fingerprint,
    selectedProfileId: null,
    pendingAction: null,
    lastError: null,
    revisionConflict: false,
  }
  const external = active(replaceAssistanceAt(initial.definition, 1, 850), 2)
  const restarted = {
    ...external,
    activation_revision: 1,
    fingerprint: "restart-fingerprint",
  }

  const retained = reconcileActiveCurve(state, external)
  const advanced = reconcileActiveCurve(
    { ...state, draft: initial.definition },
    external
  )
  const retainedAcrossRestart = reconcileActiveCurve(state, restarted)

  assert.equal(retained.draft, dirty)
  assert.equal(retained.draftBaseActivationRevision, 1)
  assert.equal(retained.draftBaseFingerprint, initial.fingerprint)
  assert.equal(deriveEditorStatus(retained, []).activeChangedExternally, true)
  assert.equal(
    deriveEditorStatus(retainedAcrossRestart, []).activeChangedExternally,
    true
  )
  assert.equal(advanced.draft, external.definition)
  assert.equal(advanced.draftBaseActivationRevision, 2)
  assert.equal(advanced.draftBaseFingerprint, external.fingerprint)
})

test("same-revision active updates adopt authoritative provenance and status", () => {
  const initial = active()
  const dirty = replaceAssistanceAt(initial.definition, 2, 810)
  const state: CurveEditorState = {
    active: initial,
    draft: dirty,
    draftBaseActivationRevision: initial.activation_revision,
    draftBaseFingerprint: initial.fingerprint,
    selectedProfileId: null,
    pendingAction: null,
    lastError: null,
    revisionConflict: false,
  }
  const incoming: ActiveSteeringCurve = {
    ...initial,
    status: "activation_failed",
    saved_profile_id: "11111111-1111-4111-8111-111111111111",
    saved_profile_revision: 3,
  }

  const reconciled = reconcileActiveCurve(state, incoming)

  assert.equal(reconciled.active, incoming)
  assert.equal(reconciled.active.saved_profile_id, incoming.saved_profile_id)
  assert.equal(
    reconciled.active.saved_profile_revision,
    incoming.saved_profile_revision
  )
  assert.equal(reconciled.active.status, "activation_failed")
  assert.equal(reconciled.draft, dirty)
  assert.equal(reconciled.draftBaseActivationRevision, 1)
  assert.equal(reconciled.draftBaseFingerprint, initial.fingerprint)
})
