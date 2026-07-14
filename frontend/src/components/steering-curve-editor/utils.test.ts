import assert from "node:assert/strict"
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
  evaluateLinearCurve,
  normalizeAssistanceAt,
  reconcileActiveCurve,
  replaceAssistanceAt,
  speedDeciKphToKph,
} from "./utils.ts"

const definition = (
  values = [1000, 890, 780, 670, 380, 0, 0, 0]
): SteeringCurveDefinition => ({
  schema_version: 1,
  interpolation: "linear-v1",
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

test("linear evaluation holds endpoints and uses the selected definition", () => {
  const activeDefinition = definition()
  const draftDefinition = replaceAssistanceAt(activeDefinition, 1, 800)
  assert.equal(evaluateLinearCurve(activeDefinition, -5), 1000)
  assert.equal(evaluateLinearCurve(activeDefinition, 5), 945)
  assert.equal(evaluateLinearCurve(activeDefinition, 300), 0)
  assert.equal(evaluateLinearCurve(activeDefinition, 10), 890)
  assert.equal(evaluateLinearCurve(draftDefinition, 10), 800)
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
