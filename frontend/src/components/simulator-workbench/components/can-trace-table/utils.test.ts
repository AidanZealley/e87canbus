import assert from "node:assert/strict"
import test from "node:test"

import type { CanTraceEntry } from "../../types.ts"
import { decodeLedSnapshot, decodeMeaning } from "./utils.ts"

const ledFrame = (data_hex: string): CanTraceEntry => ({
  type: "frame",
  session_id: 1,
  sequence: 1,
  network: "kcan",
  source: "pi",
  arbitration_id: 0x701,
  arbitration_id_hex: "0x701",
  data_hex,
  is_extended_id: false,
  monotonic_s: 0,
})

test("LED snapshots decode even indices from low nibbles", () => {
  assert.deepEqual(decodeLedSnapshot("0312540000000000"), [
    3, 0, 2, 1, 4, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  ])
  assert.equal(
    decodeMeaning(ledFrame("0312540000000000")),
    "LEDs 3 0 2 1 4 5 0 0 0 0 0 0 0 0 0 0"
  )
})

test("LED trace decoding rejects wrong lengths, characters, and colour nibbles", () => {
  assert.equal(decodeLedSnapshot("0000"), null)
  assert.equal(decodeLedSnapshot("000000000000000g"), null)
  assert.equal(decodeLedSnapshot("00000000000000g0"), null)
  assert.equal(decodeLedSnapshot("0000000000000060"), null)
  assert.equal(
    decodeMeaning(ledFrame("0000000000000060")),
    "malformed LED snapshot"
  )
})
