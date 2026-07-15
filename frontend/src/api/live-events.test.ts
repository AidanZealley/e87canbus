import assert from "node:assert/strict"
import test from "node:test"

import { classifyLiveEnvelope } from "./live-events.ts"

const envelope = (boot_id: string, revision: number, protocol_version = 1) => ({
  protocol_version,
  boot_id,
  revision,
})

test("live envelopes reset on a new boot and reject stale topic revisions", () => {
  assert.equal(classifyLiveEnvelope("old", 8, envelope("new", 1)), "reset")
  assert.equal(classifyLiveEnvelope("boot", 8, envelope("boot", 9)), "apply")
  assert.equal(classifyLiveEnvelope("boot", 8, envelope("boot", 8)), "ignore")
  assert.equal(classifyLiveEnvelope("boot", 8, envelope("boot", 7)), "ignore")
  assert.equal(
    classifyLiveEnvelope("boot", 8, envelope("boot", 9, 2)),
    "incompatible",
  )
})
