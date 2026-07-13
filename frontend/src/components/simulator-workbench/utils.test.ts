import assert from "node:assert/strict"
import test from "node:test"

import type { CanTraceEntry, SimulatorSnapshot } from "./types.ts"
import {
  mergeSnapshot,
  reduceSimulatorEvent,
  type WorkbenchSnapshot,
} from "./utils.ts"

const snapshot = (trace: CanTraceEntry[] = []): WorkbenchSnapshot => ({
  application: {
    vehicle_speed_kph: 0,
    speed_valid: false,
    steering_mode: "auto",
    manual_assistance_level: 0,
    maximum_assistance_active: false,
  },
  next_pressed: true,
  led_colours: {},
  networks: [],
  trace,
})

const frame = (sequence: number): CanTraceEntry => ({
  type: "frame",
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

test("LED update events change only the addressed colour", () => {
  const current = { ...snapshot(), led_colours: { 0: 3 } }

  const result = reduceSimulatorEvent(current, {
    type: "led_update",
    button_index: 3,
    colour_code: 5,
    colour_name: "white",
  })

  assert.deepEqual(result.led_colours, { 0: 3, 3: 5 })
})
