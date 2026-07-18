import assert from "node:assert/strict"
import test from "node:test"

import type { TraceRow as CanTraceEntry } from "@/api/live-contract.gen"
import { decodeMeaning } from "./utils.ts"

const buttonFrame = (data_hex: string): CanTraceEntry => ({
  type: "frame",
  session_id: 1,
  sequence: 1,
  network: "kcan",
  source: "pi",
  arbitration_id: 0x700,
  arbitration_id_hex: "0x700",
  data_hex,
  is_extended_id: false,
  monotonic_s: 0,
})

test("button events decode on the remaining direct button-pad ID", () => {
  assert.equal(decodeMeaning(buttonFrame("0301")), "button 3 pressed")
})

test("button trace decoding rejects malformed direct payloads", () => {
  assert.equal(decodeMeaning(buttonFrame("0002")), "malformed button event")
})
