import assert from "node:assert/strict"
import test from "node:test"
import { QueryClient } from "@tanstack/react-query"

import { applySimulatorEvent, simulatorQueryKey } from "./cache.ts"
import { emptySnapshot, type WorkbenchSnapshot } from "./utils.ts"

test("frame events update only the cached trace slice", () => {
  const queryClient = new QueryClient()
  queryClient.setQueryData<WorkbenchSnapshot>(simulatorQueryKey, emptySnapshot)

  applySimulatorEvent(queryClient, {
    type: "frame",
    session_id: 0,
    sequence: 1,
    network: "kcan",
    source: "neotrellis",
    arbitration_id: 0x700,
    arbitration_id_hex: "0x700",
    data_hex: "0001",
    is_extended_id: false,
    monotonic_s: 0,
  })

  const updated = queryClient.getQueryData<WorkbenchSnapshot>(simulatorQueryKey)
  assert.equal(updated?.trace.length, 1)
  assert.equal(updated?.application, emptySnapshot.application)
  assert.equal(updated?.led_colours, emptySnapshot.led_colours)
  assert.equal(updated?.networks, emptySnapshot.networks)
})
