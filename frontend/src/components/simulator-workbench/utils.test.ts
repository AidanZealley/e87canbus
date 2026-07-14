import assert from "node:assert/strict"
import test from "node:test"

import type { CanTraceEntry, SimulatorSnapshot } from "./types.ts"
import {
  emptySnapshot,
  formatSteeringReason,
  mergeSnapshot,
  reduceSimulatorEvent,
  type WorkbenchSnapshot,
} from "./utils.ts"

const snapshot = (
  trace: CanTraceEntry[] = [],
  session_id = 1,
  revision = 1
): WorkbenchSnapshot => ({
  session_id,
  revision,
  fatal: false,
  application: {
    vehicle_speed_kph: 0,
    speed_valid: false,
    steering_mode: "auto",
    manual_assistance_level: 0,
    maximum_assistance_active: false,
    active_steering_curve: null,
  },
  steering_controller: {
    effective_assistance: 0,
    last_command_reason: "speed_never_observed",
    watchdog_timed_out: false,
  },
  next_pressed: true,
  led_colours: Array(16).fill(0) as number[],
  networks: [],
  trace,
})

test("steering command reasons are formatted for display", () => {
  assert.equal(
    formatSteeringReason("speed_never_observed"),
    "speed never observed"
  )
  assert.equal(formatSteeringReason("inbox_overflow"), "inbox overflow")
  assert.equal(formatSteeringReason(null), "No command accepted")
  assert.deepEqual(emptySnapshot.steering_controller, {
    effective_assistance: 0,
    last_command_reason: null,
    watchdog_timed_out: false,
  })
})

const frame = (sequence: number, session_id = 1): CanTraceEntry => ({
  type: "frame",
  session_id,
  sequence,
  network: "kcan",
  source: "neotrellis",
  arbitration_id: 0x700,
  arbitration_id_hex: "0x700",
  data_hex: "0001",
  is_extended_id: false,
  monotonic_s: 0,
})

test("slim snapshots keep the existing trace", () => {
  const current = snapshot([frame(1)])
  const next: SimulatorSnapshot = {
    ...current,
    trace: undefined,
  }

  const result = mergeSnapshot(current, next)

  assert.deepEqual(result.trace, [frame(1)])
})

test("snapshots replace the complete LED state", () => {
  const current = { ...snapshot(), led_colours: Array(16).fill(1) as number[] }
  const next = {
    ...snapshot([], current.session_id, current.revision + 1),
    led_colours: Array(16).fill(2) as number[],
  }

  const result = mergeSnapshot(current, next)

  assert.deepEqual(result.led_colours, Array(16).fill(2))
  assert.notEqual(result.led_colours, next.led_colours)
})

test("malformed LED snapshots do not throw or replace any LED", () => {
  const prior = Array.from({ length: 16 }, (_, index) => index % 6)
  const current = { ...snapshot(), led_colours: prior }

  const malformedValues: unknown[] = [
    null,
    "0000000000000000",
    { length: 16 },
    Array(15).fill(2) as number[],
    [...Array(15).fill(2), 6] as number[],
  ]
  for (const malformed of malformedValues) {
    const next = {
      ...snapshot([], current.session_id, current.revision + 1),
      led_colours: malformed,
    } as unknown as SimulatorSnapshot

    const result = mergeSnapshot(current, next)

    assert.equal(result.led_colours, prior)
    assert.deepEqual(result.led_colours, prior)
  }
})

test("frame events append once and remain capped", () => {
  const current = snapshot(
    Array.from({ length: 2_000 }, (_, index) => frame(index + 1))
  )

  const appended = reduceSimulatorEvent(current, frame(2_001))
  const duplicate = reduceSimulatorEvent(appended, frame(2_001))

  assert.equal(appended.trace.length, 2_000)
  assert.equal(appended.trace[0]?.sequence, 2)
  assert.deepEqual(duplicate.trace, appended.trace)
})

test("older snapshots cannot regress state within a session", () => {
  const current = {
    ...snapshot([], 1, 3),
    application: {
      ...snapshot().application,
      steering_mode: "manual" as const,
    },
  }
  const stale = snapshot([], 1, 2)

  assert.equal(reduceSimulatorEvent(current, staleEvent(stale)), current)
})

test("a new session replaces state and clears trace", () => {
  const current = snapshot([frame(4)], 1, 4)
  const reset = snapshot([], 2, 1)

  assert.deepEqual(reduceSimulatorEvent(current, staleEvent(reset)), reset)
})

test("out-of-order and duplicate frames remain ordered once", () => {
  const current = snapshot([frame(1)], 1, 1)
  const later = reduceSimulatorEvent(current, frame(3))
  const ordered = reduceSimulatorEvent(later, frame(2))
  const duplicate = reduceSimulatorEvent(ordered, frame(2))
  const oldSession = reduceSimulatorEvent(duplicate, frame(4, 0))

  assert.deepEqual(
    ordered.trace.map((entry) => entry.sequence),
    [1, 2, 3]
  )
  assert.equal(duplicate, ordered)
  assert.equal(oldSession, ordered)
})

const staleEvent = (value: SimulatorSnapshot) => ({
  type: "snapshot" as const,
  session_id: value.session_id,
  revision: value.revision,
  snapshot: value,
})
