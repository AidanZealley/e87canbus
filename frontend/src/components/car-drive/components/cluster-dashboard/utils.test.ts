import assert from "node:assert/strict"
import { test } from "vitest"

import {
  deriveTachScale,
  padRpmDigits,
  padSpeedDigits,
  tachNeedlePosition,
  tachSegmentReached,
} from "./utils"

test("rules the strip in whole thousands past the redline", () => {
  const { ceilingRpm, segments } = deriveTachScale({
    redlineRpm: 7200,
    shiftStage1Rpm: 6800,
  })

  assert.equal(ceilingRpm, 8000)
  assert.deepEqual(
    segments.map((segment) => segment.label),
    [null, 1, 2, 3, 4, 5, 6, 7]
  )
})

test("keeps a redline on a thousand inside the strip", () => {
  // A 7000 redline must not land on the strip's right edge, where the needle
  // would be indistinguishable from an over-range reading.
  const { ceilingRpm } = deriveTachScale({
    redlineRpm: 7000,
    shiftStage1Rpm: 6600,
  })

  assert.equal(ceilingRpm, 8000)
})

test("marks every segment the shift stage reaches into", () => {
  const { segments } = deriveTachScale({
    redlineRpm: 7200,
    shiftStage1Rpm: 6800,
  })

  assert.deepEqual(
    segments
      .filter((segment) => segment.warn)
      .map((segment) => segment.startRpm),
    [6000, 7000]
  )
})

test("lights every segment rule the needle has reached", () => {
  const { segments } = deriveTachScale({
    redlineRpm: 7200,
    shiftStage1Rpm: 6800,
  })
  const lit = (rpm: number | null) =>
    segments
      .filter((segment) => tachSegmentReached(rpm, segment.startRpm))
      .map((segment) => segment.startRpm)

  // Cumulative: the rules fill in behind the needle rather than one moving.
  assert.deepEqual(lit(3260), [0, 1000, 2000, 3000])
  assert.deepEqual(lit(4000), [0, 1000, 2000, 3000])
  assert.deepEqual(lit(4001), [0, 1000, 2000, 3000, 4000])
  // A stopped engine lights nothing, and neither does lost telemetry.
  assert.deepEqual(lit(0), [])
  assert.deepEqual(lit(null), [])
})

test("pads the speed to one width without padding the announced value", () => {
  assert.deepEqual(padSpeedDigits(0), { pad: "00", digits: "0" })
  assert.deepEqual(padSpeedDigits(7), { pad: "00", digits: "7" })
  assert.deepEqual(padSpeedDigits(25), { pad: "0", digits: "25" })
  assert.deepEqual(padSpeedDigits(125), { pad: "", digits: "125" })
  // Lost telemetry holds the same width rather than collapsing the readout.
  assert.deepEqual(padSpeedDigits(null), { pad: "", digits: "---" })
})

test("pads the engine speed to the width its own strip can show", () => {
  assert.deepEqual(padRpmDigits(850, 8000), { pad: "0", digits: "850" })
  assert.deepEqual(padRpmDigits(3260, 8000), { pad: "", digits: "3260" })
  assert.deepEqual(padRpmDigits(null, 8000), { pad: "", digits: "----" })
  // A five-figure ceiling widens the readout rather than truncating it.
  assert.deepEqual(padRpmDigits(3260, 12000), { pad: "0", digits: "3260" })
})

test("clamps the needle to the strip", () => {
  assert.equal(tachNeedlePosition(4000, 8000), 0.5)
  assert.equal(tachNeedlePosition(9999, 8000), 1)
  assert.equal(tachNeedlePosition(null, 8000), 0)
})
